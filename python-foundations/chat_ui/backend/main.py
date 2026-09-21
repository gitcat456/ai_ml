
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
):
    # ---------------------------------
    # 1. Validate filename
    # ---------------------------------

    if not file.filename:
        raise HTTPException(
            status_code=400,
            detail="A filename is required.",
        )

    filename = Path(
        file.filename
    ).name

    if not filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are allowed.",
        )


    # ---------------------------------
    # 2. Read the uploaded file
    # ---------------------------------

    file_content = await file.read()

    if not file_content:
        raise HTTPException(
            status_code=400,
            detail="The uploaded file is empty.",
        )


    # ---------------------------------
    # 3. Validate the actual PDF
    # ---------------------------------
    #
    # MIME type is not enough.
    # We check the actual file contents.

    if not file_content.startswith(
        b"%PDF-"
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "The uploaded file is not a valid PDF. "
                "The file may have a .pdf extension but "
                "does not contain a valid PDF document."
            ),
        )


    # ---------------------------------
    # 4. Try parsing the PDF
    # ---------------------------------

    try:
        reader = PdfReader(
            BytesIO(file_content)
        )

        if len(reader.pages) == 0:
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


    # ---------------------------------
    # 5. Save the file
    # ---------------------------------

    file_path = (
        UPLOAD_DIR / filename
    )

    try:
        with open(
            file_path,
            "wb",
        ) as buffer:
            buffer.write(file_content)

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail="Failed to save the uploaded document.",
        ) from error


    # ---------------------------------
    # 6. Index the document
    # ---------------------------------

    try:
        ingestion_result = (
            rag.ingest_document(
                str(file_path)
            )
        )

    except Exception as error:
        # If indexing fails, remove the file
        # so we don't leave a document that
        # exists on disk but isn't in the index.

        if file_path.exists():
            file_path.unlink()

        raise HTTPException(
            status_code=500,
            detail=(
                "The PDF was valid, but the document "
                "could not be indexed."
            ),
        ) from error


    # ---------------------------------
    # 7. Success
    # ---------------------------------

    return {
        "message": (
            "Document uploaded and indexed successfully."
        ),
        "filename": filename,
        "documents": ingestion_result.get(
            "documents",
            0,
        ),
        "nodes": ingestion_result.get(
            "nodes",
            0,
        ),
    }


@app.get("/api/documents")
def list_documents(
    current_user: models.User = Depends(
        require_admin
    ),
):
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

