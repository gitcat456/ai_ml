#Write a regex that matches exactly 4 digits.

import re 

exp = "43, FWE234, 3564, 875, AB3453"

pattern = re.compile(r"\d{4}")

match = pattern.search(exp)

print(match)

