#Write a regex that matches a Kenyan phone number in the form 0712345678

import re 

pattern = re.compile(r"07\d{8}")

match = pattern.search("01120324, 07083912380912, 42892234, 0789567472, 07083912380912")

print(match)