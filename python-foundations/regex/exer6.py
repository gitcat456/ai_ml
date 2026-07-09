import re 

pattern = re.compile(r"[\w-]+@[A-za-z0-9-]+(\.[A-za-z]{2,})+")

while True:
    
    email = input("Enter email:")
    
    if pattern.fullmatch(email):
        print("Email Recorded")
        break
    
    else:
        print("Invalid email address!")