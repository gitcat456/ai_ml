from fastapi import FastAPI

app = FastAPI(
    title="Organization Chatbot API",
    description="Backend API for the organization's AI chatbot.",
    version="1.0.0",
)


@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "service": "organization-chatbot",
    }