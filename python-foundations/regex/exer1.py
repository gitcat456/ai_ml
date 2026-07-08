import re 

names = "john_123!! mary@2026 ALICE#01"

pattern = re.compile(r"[A-Za-z0-9]")

print(pattern.findall(names))