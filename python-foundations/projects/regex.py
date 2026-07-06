import re

text = """
CS2025001
CS2025123
ABC123
CS2025999
"""
stud_ids = re.compile(r"CS\d{7}")

match =stud_ids.search(text)
    
print(match.group())
