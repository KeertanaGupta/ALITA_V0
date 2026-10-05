# ALITA — Offline Multimodal RAG Platform

> Chat with your documents **fully offline**. ALITA turns PDFs (including scanned ones) into a searchable knowledge base and answers questions with cited sources, using local LLMs through Ollama. No data leaves your machine.

![Python](https://img.shields.io/badge/Python-3.12+-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)
![Django](https://img.shields.io/badge/Django_REST-092E20?logo=django&logoColor=white)
![React](https://img.shields.io/badge/React_19-61DAFB?logo=react&logoColor=black)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-4169E1?logo=postgresql&logoColor=white)
![Ollama](https://img.shields.io/badge/Ollama-local_LLMs-000000)
![FAISS](https://img.shields.io/badge/FAISS-vector_search-0467DF)

---

## ✨ Features

- **100% offline & private.** Embeddings, reranking, OCR and generation all run locally.
- **Project workspaces.** Group documents into projects and scope questions to a project or to specific documents.
- **Robust PDF ingestion.** Native text extraction with PyMuPDF, **OCR fallback** with Tesseract for scanned pages, table detection, and boilerplate/duplicate-line cleanup.
- **Parent–child chunking.** Large parent chunks (2,200 chars) for context and small child chunks (850 chars) for precise retrieval, with page-stitching across page breaks.
- **Advanced hybrid retrieval:**
  - Dense search (FAISS + `BAAI/bge-small-en-v1.5`) **+** sparse BM25
  - Multi-query expansion and **HyDE** (hypothetical document embeddings)
  - **Cross-encoder reranking** (`ms-marco-MiniLM-L-6-v2`)
  - Context compression before generation
- **Answers with citations.** Every answer links back to the source document and page, and you can open the PDF in-app.
- **Question-aware answering.** Detects question type (fact, comparison, explanation, bio, decision) and formats the answer accordingly, including comparison tables and follow-up suggestions.
- **Entity-aware filtering.** Keeps answers about "person X" from mixing in content from other people's documents (useful for resumes).
- **Image Q&A.** Ask questions about an uploaded image via the local `moondream` vision model.
- **Model switching at runtime.** Swap between Mistral, Llama 3.1 and Phi-3 from the Settings page.
- **Chat history.** Multiple chat sessions, persisted in the browser.
- **Built-in evaluation.** `/api/v1/evaluate` runs test cases and reports confidence and retrieval metrics.

---

## 🏗️ Architecture

ALITA is split into three services:

```
┌──────────────────────┐      REST       ┌──────────────────────────┐
│  Frontend (React)    │ ──────────────▶ │  Backend Core (Django)   │
│  Vite · Tailwind     │                 │  DRF · PostgreSQL        │
│  :5173               │                 │  projects, documents,    │
└──────────┬───────────┘                 │  file storage  :8000     │
           │                             └────────────┬─────────────┘
           │  chat / stats / models                   │ post_save signal
           ▼                                          ▼ (background thread)
┌──────────────────────────────────────────────────────────────────┐
│  AI Engine (FastAPI)  :8001                                      │
│  PyMuPDF + Tesseract → chunking → BGE embeddings → FAISS + BM25  │
│  → multi-query / HyDE → cross-encoder rerank → Ollama LLM        │
└──────────────────────────────────────┬───────────────────────────┘
                                       ▼
                             Ollama  :11434
                  (mistral · llama3.1 · phi3 · moondream)
```

**Ingestion flow:** when a PDF is uploaded, Django saves it and a `post_save` signal triggers the AI Engine in a background thread. The engine extracts, chunks, embeds and indexes the document, then Django updates its status (`PENDING → PROCESSING → COMPLETED / FAILED`). Deleting a document or project removes its files and its vectors from the index.

---

## 📁 Project Structure

```
ALITA_V0/
├── ai_engine/                 # FastAPI RAG microservice
│   ├── main.py                # API routes + retrieval pipeline
│   ├── schemas.py             # Pydantic request/response models
│   └── services/
│       ├── document_processor.py  # PDF text, OCR, tables
│       ├── chunking_service.py    # parent/child chunking
│       ├── vector_store.py        # FAISS index + manifest
│       ├── llm_service.py         # prompting, formatting, vision
│       └── entity_service.py      # entity detection & filtering
├── backend_core/              # Django REST backend
│   ├── alita_core/            # settings, urls
│   └── workspace/             # Project & Document models, API, signals
└── frontend/                  # React + Vite UI
    └── src/pages/             # Projects, Document Studio, Insight Engine,
                               # Knowledge Base, Settings
```

---

## 🚀 Getting Started

### Prerequisites

- Python **3.12+** and Node.js **18+**
- PostgreSQL
- [Ollama](https://ollama.com), with the models pulled:
  ```bash
  ollama pull mistral
  ollama pull moondream      # for image Q&A
  # optional: ollama pull llama3.1 && ollama pull phi3
  ```
- [Tesseract OCR](https://github.com/tesseract-ocr/tesseract) (for scanned PDFs)

### 1. Clone

```bash
git clone https://github.com/KeertanaGupta/ALITA_V0.git
cd ALITA_V0
```

### 2. AI Engine (port 8001)

```bash
cd ai_engine
python -m venv venv_ai && source venv_ai/bin/activate   # Windows: venv_ai\Scripts\activate
pip install -r requirements.txt --extra-index-url https://download.pytorch.org/whl/cu124
# CPU only? Install torch from https://pytorch.org first, then the rest.
uvicorn main:app --port 8001 --reload
```

### 3. Backend Core (port 8000)

Create `backend_core/.env`:

```env
DJANGO_SECRET_KEY=generate-a-long-random-string
DJANGO_DEBUG=True
DB_NAME=alita
DB_USER=postgres
DB_PASSWORD=your_password
DB_HOST=localhost
DB_PORT=5432
```

```bash
cd backend_core
python -m venv venv_django && source venv_django/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver 8000
```

### 4. Frontend (port 5173)

```bash
cd frontend
npm install
npm run dev
```

Open **http://localhost:5173**, create a project, upload PDFs, and start asking questions in the **Insight Engine**.

### Optional environment variables (AI Engine)

| Variable | Default | Purpose |
|---|---|---|
| `ALITA_DEVICE` | auto (`cuda` / `cpu`) | Device for embeddings & reranker |
| `ALITA_EMBEDDING_MODEL` | `BAAI/bge-small-en-v1.5` | Embedding model |
| `ALITA_HYDE_MODEL` | `mistral` | Ollama model used for HyDE |

---

## 🔌 API Reference

### AI Engine (`http://localhost:8001`)

| Method | Endpoint | Description |
|---|---|---|
| GET | `/health` | Health check |
| POST | `/api/v1/process-document` | Extract, chunk and index a PDF |
| POST | `/api/v1/chat` | Ask a question (optional `project_id`, `document_ids`, `image_data`) |
| GET | `/api/v1/stats` | Active model, index size, chunk count |
| POST | `/api/v1/models/switch` | Change the active Ollama model |
| POST | `/api/v1/debug-retrieval` | Inspect retrieved chunks for a question |
| POST | `/api/v1/delete-document` | Remove a document's vectors |
| POST | `/api/v1/delete-project` | Remove a project's vectors |
| GET/POST | `/api/v1/evaluate` | Run the evaluation suite |

Interactive docs: **http://localhost:8001/docs**

### Backend Core (`http://localhost:8000/api/v1/workspace/`)

| Resource | Endpoints |
|---|---|
| Projects | `projects/` — list, create, retrieve, update, delete |
| Documents | `documents/` — upload, list, retrieve, delete |

**Example chat request:**

```bash
curl -X POST http://localhost:8001/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"question": "Summarize the key findings", "project_id": "all"}'
```

---

## 🖼️ Screenshots

<!-- Add screenshots/GIF here, e.g. -->
<!-- ![Insight Engine](docs/insight-engine.png) -->

---

## 🗺️ Roadmap

- [ ] Audio transcription (Whisper) and code-repository ingestion
- [ ] Docker Compose setup for one-command startup
- [ ] Replace background threads with a task queue (Celery/RQ)
- [ ] Authentication and per-user workspaces
- [ ] Streaming responses

---

## 👩‍💻 Author

**Keertana Gupta** — [GitHub](https://github.com/KeertanaGupta) · [LinkedIn](https://www.linkedin.com/in/keertanagupta/)

If you find this project useful, consider giving it a ⭐!
