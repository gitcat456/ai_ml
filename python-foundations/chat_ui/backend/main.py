from fastapi import FastAPI, UploadFile, File
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from rag.service import RAGService
from pathlib import Path

app = FastAPI()


UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

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

class ChatRequest(BaseModel):
    session_id: str
    message: str


@app.get("/")
def root():
    return {"message": "Chat UI backend is running"}


@app.post("/api/chat")
def chat(request: ChatRequest):
    response = rag.chat(request.session_id, request.message)

    return response

@app.post("/api/documents/upload")
async def upload_document(file: UploadFile = File(...)):
    if file.content_type != "application/pdf":
        return {
            "error": "Only PDF files are allowed."
        }

    file_path = UPLOAD_DIR / file.filename

    with open(file_path, "wb") as buffer:
        buffer.write(await file.read())

    rag.ingest_document(str(file_path))

    return {
        "message": "Document uploaded and indexed successfully.",
        "filename": file.filename,
    }
    
@app.get("/api/documents")
def list_documents():
    documents = []

    for file_path in UPLOAD_DIR.iterdir():
        if file_path.is_file() and file_path.suffix.lower() == ".pdf":
            documents.append({
                "filename": file_path.name,
                "size": file_path.stat().st_size,
            })

    return {
        "documents": documents
    }
    
@app.delete("/api/documents/{filename}")
def delete_document(filename: str):
    file_path = UPLOAD_DIR / filename

    if not file_path.exists():
        return {
            "error": "Document not found."
        }

    deleted = rag.delete_document(filename)

    if not deleted:
        return {
            "error": "Document is not indexed."
        }

    file_path.unlink()

    return {
        "message": "Document deleted successfully.",
        "filename": filename,
    }