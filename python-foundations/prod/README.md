# EUSDA AI Chatbot Service (Production)

Official production AI assistant service for **EUSDA** (Egerton University Seventh-day Adventist Church / Association), built with **FastAPI**, **Groq LLM**, **HuggingFace Embeddings**, **SentenceTransformer Cross-Encoder Reranking**, and **Structured Grounding & Inline Fact Citations**.

---

## 🏗️ System Architecture

```text
User Request (EUSDA Website Frontend / Chat Widget)
           │
           ▼
 Express Backend Proxy (/api/chat)
           │
           ▼
 Python FastAPI AI Service (POST /api/chat)
           │
 ┌─────────┴──────────────────────────────────────────┐
 │ 1. Query Router                                    │
 │  ├── Regex Fast-Path (Greetings/Intros/Farewells)  │
 │  └── Fast LLM Intent Classifier                    │
 └─────────┬────────────────────────────────┬─────────┘
           │                                │
   [DIRECT / OUT_OF_SCOPE]              [KNOWLEDGE]
           │                                │
   Conversational Reply             Smart Pronoun-Gated Query Rewrite
           │                                │
           │                        LlamaIndex + HuggingFace Vector Search
           │                                │
           │                        SentenceTransformer Reranking (top_n=5)
           │                                │
           │                        Scope Validation Guard (Relevance Check)
           │                                │
           └────────────────┬───────────────┘
                            │
                            ▼
           Grounded Groq LLM Answer Generation
              (with inline fact citations)
                            │
                            ▼
              Structured JSON Response:
            { "answer": "...", "sources": [...] }
```

---

## 🚀 Key Features & Production Engineering

1. **Intelligent Conversational Memory & Routing (`app/chatbot/router.py`, `app/chatbot/memory.py`)**:
   - **Multi-Turn Context**: Maintains conversational history so users can have smooth, natural dialogues.
   - **Personalized Member Greetings**: Understands self-introductions (e.g., *"hello there am Denz a church member"*) and responds with a warm, welcoming Christian fellowship greeting rather than a static canned response.
   - **Sub-Millisecond Regex Fast-Path**: Instantly identifies common greetings, farewells, math/trivia out-of-scope queries without making expensive LLM calls.
   - **Fast Intent Classifier**: Lightweight classification into `DIRECT`, `KNOWLEDGE`, and `OUT_OF_SCOPE`.

2. **Ultra-Fast RAG Pipeline with Smart Query Rewriting (`app/chatbot/service.py`)**:
   - **Pronoun-Gated Rewriting**: Only rewrites queries when referential pronouns (*"he"*, *"they"*, *"what about his role"*, *"why"*) are detected, eliminating redundant LLM round-trips for standalone questions.
   - **Pre-warmed Vector Index**: HuggingFace embeddings (`BAAI/bge-small-en-v1.5`) pre-warmed during lifespan startup.
   - **Cross-Encoder Reranking**: `cross-encoder/ms-marco-MiniLM-L-2-v2` guarantees top-ranked semantic chunks.

3. **Clean Citations & Structural Document Metadata (`app/knowledge/retriever.py`, `app/schemas.py`)**:
   - **Zero Internal Filename Exposure**: Raw `.pdf` extensions are stripped and mapped to clean, human-readable document titles (e.g. *EUSDA Constitution*, *SDA Church Manual*).
   - **Hierarchical Document Parsing**: Automatically detects and extracts Articles (e.g. *Article 4: EUSDA Offices and Officers*), Sections (e.g. *Section D: Officers Duties*), Chapters, and Pages.
   - **Inline Fact Badges**: Every factual statement generated in the answer is followed by an inline citation badge:
     `...are religious leaders of the church who conduct services [EUSDA Constitution, Art. 4, Sec. D, p. 15].`
   - **Rich Source Objects**: Response includes structured metadata (`document_title`, `article`, `section`, `chapter`, `page`, `citation_label`, `excerpt`, and backward-compatible `filename`).

4. **Strict Grounding & Evidence Scope Guard (`app/knowledge/scope_guard.py`)**:
   - Validates that retrieved evidence directly supports the user query before passing it to generation.
   - Prevents hallucinations and blocks prompt injection.

---

## 🛠️ Setup & Execution

### 1. Requirements
Ensure Python 3.10+ is installed in your virtual environment:
```bash
pip install -r requirements.txt
```

### 2. Environment Configuration
Create or update `.env`:
```env
GROQ_API_KEY=your_groq_api_key_here
LLM_MODEL=qwen/qwen3.8-27b
FAST_LLM_MODEL=qwen/qwen3.8-27b
EMBEDDING_MODEL=BAAI/bge-small-en-v1.5
RERANKER_MODEL=cross-encoder/ms-marco-MiniLM-L-2-v2
APP_ENV=development
```

### 3. Document Ingestion (Rebuilding Index)
To ingest documents from `data/documents/`:
```bash
python -m app.knowledge.ingest
```

### 4. Running the Server
Start the FastAPI server:
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

---

## 📡 API Reference

### Health Check
`GET /health`
```json
{
  "status": "ok",
  "service": "eusda-chatbot"
}
```

### Chat Endpoint
`POST /api/chat`

**Request:**
```json
{
  "session_id": "session-uuid-1234",
  "message": "what are the roles of the church elders ?"
}
```

**Response:**
```json
{
  "answer": "Based on the EUSDA Constitution and the SDA Church Manual, here are the key roles of church elders:\n\n* **Spiritual Leadership:** Elders are religious leaders who lead the church by precept and example into a deeper Christian experience [EUSDA Constitution, Art. 4, Sec. D, p. 15].\n* **Conducting Services:** They conduct church services and minister in word and doctrine [SDA Church Manual, p. 81]...",
  "sources": [
    {
      "filename": "EUSDA Constitution",
      "document_title": "EUSDA Constitution",
      "article": "ARTICLE 4",
      "section": "Section D",
      "chapter": null,
      "page": 15,
      "citation_label": "EUSDA Constitution, Art. 4, Sec. D, p. 15",
      "excerpt": "1.3 Elders The Elders shall; i) Be religious leaders of the church who must seek to lead the church by precept and example..."
    }
  ]
}
```

---

## 🧪 Testing

Run the complete test suite:
```bash
pytest
```
*55 automated tests covering API validation, citation formatting, query routing heuristics, and scope guard evaluations.*
