import re 

pattern = re.compile(r"(\d{3})-(\d{3})-(\d{4})")

match = pattern.search("Call me: 415-555-4242")

print(match.groups())

"""
    group(2) → one thing
    groups() → tuple of all captured groups
"""