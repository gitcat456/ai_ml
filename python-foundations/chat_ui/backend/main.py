from pathlib import Path

from fastapi import (
    Depends,
    FastAPI,
    File,
    HTTPException,
    UploadFile,
)
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session

import database
import models

from auth import (
    create_access_token,
    hash_password,
    verify_password,
)
from rag.service import RAGService


database.Base.metadata.create_all(
    bind=database.engine
)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


rag = RAGService()


UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)


# -------------------------
# Authentication
# -------------------------
class RegisterRequest(BaseModel):
    username: str
    password: str
    
@app.post("/api/auth/register")
def register(
    request: RegisterRequest,
    db: Session = Depends(database.get_db),
):
    existing_user = (
        db.query(models.User)
        .filter(
            models.User.username == request.username
        )
        .first()
    )

    if existing_user:
        raise HTTPException(
            status_code=400,
            detail="Username already exists.",
        )

    user = models.User(
        username=request.username,
        hashed_password=hash_password(
            request.password
        ),
        role="user",
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    return {
        "message": "User registered successfully.",
        "id": user.id,
        "username": user.username,
        "role": user.role,
    }

class LoginRequest(BaseModel):
    username: str
    password: str
    
@app.post("/api/auth/login")
@app.post("/api/auth/login")
def login(
    request: LoginRequest,
    db: Session = Depends(database.get_db),
):
    user = (
        db.query(models.User)
        .filter(
            models.User.username == request.username
        )
        .first()
    )

    if not user:
        raise HTTPException(
            status_code=401,
            detail="Invalid username or password.",
        )

    if not verify_password(
        request.password,
        user.hashed_password,
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid username or password.",
        )

    access_token = create_access_token(
        {
            "sub": str(user.id),
            "username": user.username,
            "role": user.role,
        }
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
    }


# -------------------------
# General
# -------------------------

@app.get("/")
def root():
    return {
        "message": "RAG UI backend is running"
    }


# -------------------------
# Chat
# -------------------------

class ChatRequest(BaseModel):
    session_id: str
    message: str


@app.post("/api/chat")
def chat(request: ChatRequest):
    response = rag.chat(
        request.session_id,
        request.message,
    )

    return response


# -------------------------
# Documents
# -------------------------

@app.post("/api/documents/upload")
async def upload_document(
    file: UploadFile = File(...)
):
    if file.content_type != "application/pdf":
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are allowed.",
        )

    file_path = UPLOAD_DIR / file.filename

    with open(file_path, "wb") as buffer:
        buffer.write(await file.read())

    rag.ingest_document(
        str(file_path)
    )

    return {
        "message": (
            "Document uploaded and indexed successfully."
        ),
        "filename": file.filename,
    }


@app.get("/api/documents")
def list_documents():
    documents = []

    for file_path in UPLOAD_DIR.iterdir():
        if (
            file_path.is_file()
            and file_path.suffix.lower() == ".pdf"
        ):
            documents.append(
                {
                    "filename": file_path.name,
                    "size": file_path.stat().st_size,
                }
            )

    return {
        "documents": documents
    }


@app.delete("/api/documents/{filename}")
def delete_document(filename: str):
    file_path = UPLOAD_DIR / filename

    if not file_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Document not found.",
        )

    deleted = rag.delete_document(
        filename
    )

    if not deleted:
        raise HTTPException(
            status_code=404,
            detail="Document is not indexed.",
        )

    file_path.unlink()

    return {
        "message": "Document deleted successfully.",
        "filename": filename,
    }