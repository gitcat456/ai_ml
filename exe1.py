import os

for foldername, subfolders, filenames in os.walk("python-foundations"):
    
    print("Folder:", foldername)
    print("Subfolders:", subfolders)
    print("Files:", filenames)
    print("-" * 30)
