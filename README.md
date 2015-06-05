# sandhog
A Python script to deduplicate files based on hashing

Requires Python 2.7 or later

To scan a folder and add it to the database:
sandhog.py -s [foldername]

To create a CSV report of duplicate files found in your scans:
sandhog.py -r

Currently does not update existing database entries if you rescan a folder with deleted files!

Files of note:
sandhog.py - the main script which controls the deduplication
sandhog.db (will be created after the first scan) - an SQLite database containing all the file paths, hashes, and sizes for all scanned folders
dupe_report.csv (will be created when reporting is run) - a CSV list of all the duplicate items with file sizes and hashes
error.log (will be created after the first scan) - a list of errors encountered during a scan (currently will only list files that could not be opened)