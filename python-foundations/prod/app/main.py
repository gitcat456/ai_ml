from fastapi import FastAPI

from app.api.routes import router


app = FastAPI(
    title="Organization Chatbot API",
    description="Backend API for the organization's AI chatbot.",
    version="1.0.0",
)

app.include_router(router)


@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "service": "organization-chatbot",
    }