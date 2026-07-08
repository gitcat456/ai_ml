import re

text = "user_01: Excellent service!!! user_02: Delivery was late...  user_03: ⭐⭐⭐⭐⭐"
            

pattern1 = re.compile(r"\w+\d{2}")
print(pattern1.findall(text))

pattern2 = re.compile(r"\W")
print(pattern2.findall(text))


pattern3 = re.compile(r"\s+\w+\W+")
print(pattern3.findall(text))