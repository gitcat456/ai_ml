import logging
logging.basicConfig(
    filename='loginlogs.txt',
    level=logging.DEBUG,
    format=' %(asctime)s -  %(levelname)s -  %(message)s')

logging.debug('Start of program')

username =  input("username: ")
password = input ("password: ")

logging.debug('username:' + username)
logging.debug('password:' + password)

if username == "admin" and password == "admin123":
    print("Access Granted!")
    logging.debug("Access Granted")
    
else:
    logging.debug("Access Denied")
    raise Exception("Invalid Credentials")

 

#to disable logs =  logging.disable(logging.CRITICAL)