#To do: get a date and time stamp last modified for each file, do an "update if newer" function for the DB read list, generate proper errors and dump them in a log, track scan progress and duration
#(db should not even hash a file that has not been updated since last run, unless as an option when args are implemented)

import hashlib
import sys
import os
import sqlite3
import datetime
import time

reload(sys)  
sys.setdefaultencoding('utf8')

#set our database and file defaults
dbName = 'sandhog.db'
fileHashes = 'file_hashes'
reportFile = 'dupe_report.csv'
errorLog = 'error.log'

clearRight = "\033[K"
moveUp = "\033[1A"

def lineRewrite(inString, filePath, fileSize):
    sys.stdout.write("\r" + clearRight);
    sys.stdout.write(moveUp)
    sys.stdout.write("\r" + clearRight);
    if int(fileSize) > -1:
        sys.stdout.write(" [ %12d ]" % fileSize)
    sys.stdout.write(str(filePath))
    sys.stdout.write("\n")
    sys.stdout.write(str(inString))
    sys.stdout.flush()

def md5sum(filename):
    md5 = hashlib.md5()
    with open(filename, 'rb') as f:
        #for chunk in iter(lambda: f.read(128 * md5.block_size), b''):
        for chunk in iter(lambda: f.read(8192 * md5.block_size), b''):
            md5.update(chunk)
    return md5.hexdigest()

#Stolen from stackoverflow and then tweaked
def hashfile(filepath): #This generates a hash based on file content only, but that's what we want anyway
    fileHash = hashlib.sha1()
    f = open(filepath, 'rb')
    try:
        fileHash.update(f.read() + str(os.path.getsize(filepath))) #update sha1 hash source based on file data content and file size
    finally:
        f.close()
    return fileHash.hexdigest() #generate the sha1 has based on the source info

def scanFolder(dbName, table, targetFolder, errorLog): #scans the target folder for dupes, really just hashes every readable file and puts in the DB
    startTime = time.time()
    fileNumber = 0
    errNumber = 0
    totalFiles = sum([len(files) for r, d, files in os.walk(str(targetFolder))]) #Need to str() the param to os.walk lest we hit filenames it thinks is unicode, but invalid and cause an exception
    conn = sqlite3.connect(dbName) #open or create our database to store all this stuff
    c = conn.cursor() #initialize our cursor to manipulate the DB
    # Create the  file hashes table if there isn't one already
    c.execute("CREATE TABLE IF NOT EXISTS %s (filename TEXT PRIMARY KEY, size INTEGER, device INTEGER, inode INTEGER, hash TEXT, updated TIMESTAMP)" % (fileHashes)) #Note that the filename is the full path and is a unique primary key

    errlog = open(errorLog, 'w') #open the error log file for writing
    percentComplete = 0
    for folder, dirs, files in os.walk(str(targetFolder)):
        for filename in files:
            fileNumber += 1
            try:
                targetFile = os.path.join(folder,filename)
                if os.path.isfile(targetFile):
                    fstat = os.stat(targetFile)
                    targetSize = fstat.st_size
                    targetDevice = fstat.st_dev
                    targetInode = fstat.st_ino

                    lineRewrite( "Processing %i of %i files with %i errors. (%.2f%% complete)" %
                        (fileNumber, totalFiles, errNumber, percentComplete), targetFile, targetSize ) #update status on stdout
                    #targetHash = hashfile(targetFile)
                    targetHash = md5sum(targetFile)
                    #write an entry to the file_hashes table for each file with its hash
                    c.execute("INSERT OR REPLACE INTO file_hashes(filename,size,device,inode,hash,updated) VALUES (?,?,?,?,?,?)",
                        (sqlite3.Binary(targetFile),targetSize,targetDevice,targetInode,targetHash,datetime.datetime.now()))
            except IOError as e:
                errlog.write( "Error processing: " + filename + ", " + e.strerror + "\n")
                errNumber += 1
            except OSError as e:
                errlog.write( "Error processing: " + filename + ", " + e.strerror + "\n")
                errNumber += 1
            except Exception as e:
                errlog.write( "Error processing: " + filename + ", " + str(e) + "\n")
                errNumber += 1
            percentComplete = 100 * float(fileNumber) / float(totalFiles)
    lineRewrite( "Completed %i of %i files with %i errors. (%.2f%% complete)" %
        (fileNumber, totalFiles, errNumber, percentComplete), "", -1 ) #update status on stdout
    conn.commit() #commit the changes to the DB
    conn.close()
    errlog.close()
    totalTime = time.time() - startTime
    print "\nTask complete in %s seconds" % str(datetime.timedelta(seconds=totalTime))

def runReport(dbName, table, outFile): #Generate a CSV report based on the table in the DB for items with matching hashes only NEEDS TO CHECK FOR EXISTENCE OF DB AND TABLE AND RETURN ERROR!
    dupeDiskSpace = 0
    hash2devinodes = {}
    if os.path.isfile(dbName):
        lastHash = ''
        lastInode = 0
        lastDevice = 0
        conn = sqlite3.connect(dbName) #open or create our database to store all this stuff
        conn.row_factory = sqlite3.Row
        cur = conn.cursor() #initialize our cursor to manipulate the DB
        r = open(outFile, 'w') #open the file to write the report to
        #anything with a hash matching another item in the table
        cur.execute('SELECT * FROM file_hashes WHERE hash IN (SELECT hash FROM file_hashes GROUP BY hash HAVING COUNT(*) > 1) ORDER BY size DESC, inode, hash')
        names = list(map(lambda x: x[0], cur.description))
        r.write("%s\t%s\t%s\t%s\t%s\n" % ("Size", "Hash", "Device", "Inode", "File Path")) # field names / csv header
        for row in cur:
            isHardlinked = False
            if row["hash"] not in hash2devinodes:
                hash2devinodes[row["hash"]] = []
                hash2devinodes[row["hash"]].append(dict(row))
            if lastHash != row["hash"]:
                lastHash = row["hash"]
                lastDevice = row["device"]
                lastInode = row["inode"]
            else:
                if lastInode == row["inode"] and lastDevice == row["device"]: # hardlinked
                    isHardlinked = True
                else:
                    dupeDiskSpace += row["size"]
            r.write("%10d\t%s\t%3d\t%6d\t%s%s\n"%(row["size"],
                    row["hash"], row["device"], row["inode"],
                    "\\ " if isHardlinked else "", row["filename"]) )
        r.close()
        conn.close()
    else:
        print "Database not found!"
    return dupeDiskSpace

def usage(): #provides usage instructions
    print "Usage: sandhog -s [target folder]"
    print "       sandhog -r"    

if (len(sys.argv) == 1): #check the second argument (the first argument is always the python script itself, so this would be the first command line arg)
    usage()
else:
    if (sys.argv[1] == '-s') and (len(sys.argv) == 3): #use -s to run a scan
        targetFolder = unicode(sys.argv[2]) #use the third command line argument as our target folder, cast to unicode to avoid file open problems
        if os.path.isdir(targetFolder): #make sure this is a folder and not a file or just garbage
            print "Scanning " + targetFolder
            #scan the folder
            scanFolder(dbName,fileHashes,targetFolder,errorLog)
        else:
            print "Folder not found!" #tell us it's not a folder
    elif (sys.argv[1] == "-r"): #use -r to run a report
        print "Writing report to " + reportFile
        #make a nice report - make this a function later
        dupeDiskSpace = runReport(dbName,fileHashes,reportFile)
        print "Found %.2f MB wasted space" % (dupeDiskSpace / (1024.0*1024))
    else:
        print "Invalid arguments"
