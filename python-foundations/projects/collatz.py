
def collatz(number):
    if number % 2 == 0:
        result = number // 2
    else:
        result = 3 * number + 1
    print(result)       
    return result

while True :
    try:  
     number = int(input("Enter any integer: "))
     print(number)
     break
    
    except ValueError:
        print(f"Please enter an integer!")
        
while number != 1: 
      number = collatz(number)



    