import random 
import sys

num = random.randint(1, 20)

def check_num(input, trial):
    if input == num:
        print(f"trials used: {trial + 1}")
        sys.exit()
    elif input < num:
        print("Low!")
    else:
        print("high!")
        
trials = 0      
while trials < 5:
 user_num = input("enter ur number: ")
 user_num = int(user_num)
 check_num(user_num, trials)
 trials += 1
 
 if  trials == 5 :
     print("Max Trial Limit reached!")
     
     
     
#by gpt :
import random

secret_number = random.randint(1, 20)

for attempt in range(1, 6):
    guess = int(input("Guess a number between 1 and 20: "))

    if guess == secret_number:
        print(f"Correct! You got it in {attempt} attempt(s).")
        break

    elif guess < secret_number:
        print("Too low!")

    else:
        print("Too high!")

else:
    print(f"Out of attempts! The number was {secret_number}.")
     
