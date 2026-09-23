from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

@app.get("/dashboard")
def dash():
    return {"message": "Welcome to the dashboard!"}

names = []

@app.post("/name")
def details(name):
    names.append(name)
    return {"message": "Details uploaded sucessfully"}

@app.get("/regis")
def deta():
    return {"data": names}

dbusername = "Daggo"
dbpassword = "1234"

@app.post("/login")
def details(username, password):
    if username != dbusername or password != dbpassword:
        return {"error": "Invalid credentials"}
    
    return {"message": "Login succesful"}



class Order(BaseModel):
    customer_id: int
    items: list
    
order = {
    "customer_id":"123",
    "items": [
        {
            "item_id": "tresr",
            "quantity": 5,
            "price": 679
        },
        {
            "item_id": "yvuhb",
            "quantity": 3,
            "price": 45
        }
    ]
}

@app.post("/place-order")
def process_order(order: Order):
    
    if order.items == []:
        return("Order cannot be empty!")
    
    def calculate_price():
        total_price = 0
        for item in order.items:
            item_price = item.get("price")*item["quantity"]
            total_price += item_price
        
        print("Total order amount: " , total_price)
        
    return calculate_price()
    






