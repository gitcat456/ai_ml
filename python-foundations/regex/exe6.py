import re 

pattern = re.compile(r"\(\d{2}\)")

match = pattern.search("(45)")

print(match.group())