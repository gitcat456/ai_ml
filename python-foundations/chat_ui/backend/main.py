from pypdf import PdfReader
from io import BytesIO
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
from pypdf import PdfReader
from sqlalchemy.orm import Session

import database
import models

from auth import (
    create_access_token,
    get_current_user,
    hash_password,
    require_admin,
    verify_password,
)

from rag.service import RAGService


# -------------------------
# Database
# -------------------------

database.Base.metadata.create_all(
    bind=database.engine
)


# -------------------------
# FastAPI
# -------------------------

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


# -------------------------
# RAG
# -------------------------

rag = RAGService()


# -------------------------
# Uploads
# -------------------------

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


@app.get("/api/auth/me")
def get_me(
    current_user: models.User = Depends(
        get_current_user
    ),
):
    return {
        "id": current_user.id,
        "username": current_user.username,
        "role": current_user.role,
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
def chat(
    request: ChatRequest,
    current_user: models.User = Depends(
        get_current_user
    ),
):
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
    file: UploadFile = File(...),
    current_user: models.User = Depends(
        require_admin
    ),
    db: Session = Depends(database.get_db),
):
    if not file.filename:
        raise HTTPException(
            status_code=400,
            detail="A filename is required.",
        )

    filename = Path(file.filename).name

    if not filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are allowed.",
        )

    file_content = await file.read()

    if not file_content:
        raise HTTPException(
            status_code=400,
            detail="The uploaded file is empty.",
        )

    if not file_content.startswith(b"%PDF-"):
        raise HTTPException(
            status_code=400,
            detail=(
                "The uploaded file is not a valid PDF. "
                "The file may have a .pdf extension but "
                "does not contain a valid PDF document."
            ),
        )

    # -------------------------
    # Validate PDF
    # -------------------------

    try:
        reader = PdfReader(
            BytesIO(file_content)
        )

        pages = len(reader.pages)

        if pages == 0:
            raise ValueError(
                "PDF contains no pages."
            )

    except Exception as error:
        raise HTTPException(
            status_code=400,
            detail=(
                "The uploaded PDF could not be read. "
                "Please upload a valid, uncorrupted PDF."
            ),
        ) from error

    # -------------------------
    # Prevent duplicate filename
    # -------------------------

    existing_document = (
        db.query(models.Document)
        .filter(
            models.Document.filename == filename
        )
        .first()
    )

    if existing_document:
        raise HTTPException(
            status_code=409,
            detail=(
                "A document with this filename "
                "already exists."
            ),
        )

    # -------------------------
    # Save PDF
    # -------------------------

    file_path = UPLOAD_DIR / filename

    try:
        with open(file_path, "wb") as buffer:
            buffer.write(file_content)

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail="Failed to save the uploaded document.",
        ) from error

    # -------------------------
    # Create document record
    # -------------------------

    document_record = models.Document(
        filename=filename,
        size=len(file_content),
        pages=pages,
        chunks=0,
        status="indexing",
    )

    db.add(document_record)
    db.commit()
    db.refresh(document_record)

    # -------------------------
    # Index document
    # -------------------------

    try:
        ingestion_result = rag.ingest_document(
            str(file_path)
        )

        document_record.chunks = ingestion_result.get(
            "nodes",
            0,
        )

        document_record.status = "indexed"
        document_record.error = None

        db.commit()

    except Exception as error:

        document_record.status = "failed"
        document_record.error = str(error)

        db.commit()

        raise HTTPException(
            status_code=500,
            detail=(
                "The PDF was saved, but indexing failed. "
                "The document remains available for retry."
            ),
        ) from error

    return {
        "message": (
            "Document uploaded and indexed successfully."
        ),
        "filename": filename,
        "pages": document_record.pages,
        "chunks": document_record.chunks,
        "status": document_record.status,
    }
@app.get("/api/documents")
def list_documents(
    current_user: models.User = Depends(
        require_admin
    ),
    db: Session = Depends(database.get_db),
):
    documents = (
        db.query(models.Document)
        .order_by(
            models.Document.uploaded_at.desc()
        )
        .all()
    )

    return {
        "documents": [
            {
                "id": document.id,
                "filename": document.filename,
                "size": document.size,
                "pages": document.pages,
                "chunks": document.chunks,
                "status": document.status,
                "error": document.error,
                "uploaded_at": (
                    document.uploaded_at.isoformat()
                    if document.uploaded_at
                    else None
                ),
            }
            for document in documents
        ]
    }

@app.delete("/api/documents/{filename}")
def delete_document(
    filename: str,
    current_user: models.User = Depends(
        require_admin
    ),
):
    filename = Path(
        filename
    ).name

    file_path = (
        UPLOAD_DIR / filename
    )

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


# -------------------------
# Development
# -------------------------

@app.patch("/api/dev/make-admin/{username}")
def make_admin(
    username: str,
    db: Session = Depends(database.get_db),
):
    user = (
        db.query(models.User)
        .filter(
            models.User.username == username
        )
        .first()
    )

    if not user:
        raise HTTPException(
            status_code=404,
            detail="User not found.",
        )

    user.role = "admin"
    db.commit()

    return {
        "message": "User promoted to admin.",
        "username": user.username,
        "role": user.role,
    }

