from fastapi import FastAPI

app = FastAPI()


@app.get("/")
def root():
    return {"message": "Chat UI backend is running"}

@app.get("/home")
def root():
    return {"message": "That was fast bro!!"}