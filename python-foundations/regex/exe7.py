"""Write a regex that matches either:
AI
ML
Data

using the pipe operator."""

import re 

pattern = re.compile(r"AI|ML|Data")

print(pattern.findall("In the new filed of unstructured Data...specializets use ML and ai to be able to gropu this data"))