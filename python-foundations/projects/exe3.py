#Write a regex that matches AI2026

import re 

pattern = re.compile(r"AI\d{4}")

match = pattern.search("AI435, BX2026, AI2026")

print(match.group())