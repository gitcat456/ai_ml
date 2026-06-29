age = -5

assert age >= 0, "Bad Request"

if age < 0:
    raise Exception("Age cannot be negative")