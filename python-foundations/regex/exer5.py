import re 

phone_no = input("Enter phone number: ")

pattern = re.compile(r"^(0|\+?254)(7|1)\d{8}$")

if pattern.fullmatch(phone_no):
    print("Valid")
else:
    print("Invalid Phone number")

