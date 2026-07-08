"""Write a regex that finds every lowercase letter in

Python3IsAwesome"""

import re 

pattern = re.compile(r"[a-z]+")

print(pattern.findall("Python3IsAwesome"))