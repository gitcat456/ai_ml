import re

pattern = re.compile(r"(ABC)-(\d+)")

match = pattern.search("ABC-12345")

print(match.group())
print(match.group(1))
print(match.group(2))