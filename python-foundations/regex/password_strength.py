import re

password = input("Enter password: ")

upper = re.compile(r"[A-Z]")
lower = re.compile(r"[a-z]")
digit = re.compile(r"\d")
special = re.compile(r"[^A-Za-z0-9]")
length = re.compile(r".{8,}")

    
if not length.fullmatch(password):
    print("Too short")

elif not upper.search(password):
    print("Missing uppercase")

elif not lower.search(password):
    print("Missing lowercase")

elif not digit.search(password):
    print("Missing digit")

elif not special.search(password):
    print("Missing special character")

else:
    print("Strong password")
    