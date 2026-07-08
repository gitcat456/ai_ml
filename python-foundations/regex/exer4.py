import re 

pattern = re.findall(r"^07\d{8}$","0712345678")
         
print(pattern)