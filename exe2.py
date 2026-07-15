from pathlib import Path

folder = Path("python-foundations")

"""glob() = one room
   rglob() = the whole building"""
   
for file in folder.rglob("*.csv"):
    print(file)