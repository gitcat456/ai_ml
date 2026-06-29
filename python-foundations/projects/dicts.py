import pprint
my_laptop = {
    "make": "dell",
    "struct": 180,
    "color": "grey"
}

pprint.pprint(my_laptop.items())
print(my_laptop.keys())
print(my_laptop.values())
print(my_laptop.get("maky", 0))

all_guests = {
    "Alice": {
        "Beans": "10kg",
        "Mapera": "2kg"
    },
    "Bob": {
        "Cash": 300000,
        "Cars": "BMW Cx-50"
    }
}

