# sandhog
A Python script to deduplicate files based on hashing

To scan a folder and add it to the database:
sandhog.py -s [foldername]

To create a CSV report of duplicate files found in your scans
sandhog.py -r

Currently does not update existing database entries properly!