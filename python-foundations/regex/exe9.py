"""Write a regex that finds every number in

Room45Seat12Desk8"""

import re 

pattern = re.compile(r"[^A-Za-z]")

print(pattern.findall("Room45Seat12Desk8"))