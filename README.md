# Tactical Terrain Analysis Chatbot

A locally-hosted chatbot for terrain analysis and document-backed Q&A. Given a set of coordinates, it fetches real geographic data — roads, waterways, elevation, vegetation, infrastructure, weather — and produces a structured OCOKA assessment. It also supports document ingestion (PDFs, scanned images) with OCR and semantic search, so the language model can ground its responses in uploaded material.

Everything runs on-device. No external LLM APIs, no data leaves the local network.

## Core Capabilities

### Terrain Analysis
- Accepts coordinates in decimal, DMS, or labelled formats
- Queries OpenStreetMap and Open-Meteo for real infrastructure and environmental data
- Generates OCOKA breakdowns: Observation & Fields of Fire, Cover & Concealment, Obstacles, Key Terrain, Avenues of Approach
- Computes elevation profiles, slope gradients, and movement time estimates
- Retrieves weekly weather forecasts for the target area

### Document Processing
- Ingests PDFs (digital and scanned) and images via Tesseract OCR
- Splits content into hierarchical parent/child chunks for retrieval accuracy
- Indexes everything into a persistent ChromaDB vector store
- Tracks source page numbers for traceability

### Retrieval-Augmented Generation
- Semantic search over all indexed documents using HuggingFace embeddings
- Parent-child chunk resolution: small chunks for precise matching, larger chunks for LLM context
- Conversation history support for multi-turn interactions
- Automatic routing — messages containing coordinates trigger terrain analysis; all others go through standard RAG

## Tech Stack

| Layer | Technology |
|-------|------------|
| Frontend | React 19, Tailwind CSS |
| Backend | Python 3.12+ / Flask |
| LLM | Ollama (qwen3:8b-q4_K_M, local) |
| Embeddings | BAAI/bge-large-en-v1.5 (HuggingFace) |
| Vector DB | ChromaDB |
| OCR | Tesseract (pytesseract) |
| Geographic APIs | OpenStreetMap Overpass, Open-Meteo |
| Object Detection | YOLOv8 (Ultralytics) |

## Prerequisites

- Python 3.12+
- Node.js
- Ollama installed and running (`ollama pull qwen3:8b-q4_K_M`)
- Tesseract OCR (`brew install tesseract` on macOS)

## Setup

### Backend

```bash
cd backend
pip install -r requirements.txt
```

Create a `.env` file in `backend/`:

```
OLLAMA_HOST=http://localhost:11434
```

Start the server:

```bash
python app.py
```

Runs on port 5001 by default.

### Frontend

```bash
npm install
npm start
```

Runs on port 3000, expects the backend at `http://127.0.0.1:5001`.

## API

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | System status and component health |
| `POST` | `/chat` | RAG-powered conversational query |
| `POST` | `/analyze_coordinates` | Terrain analysis for a coordinate pair |
| `POST` | `/upload` | Upload and index a document |
| `POST` | `/upload_doctrine` | Upload to the permanent knowledge base |
| `POST` | `/delete_all` | Clear all indexed data (requires `{"confirm": true}`) |

## Retrieval Pipeline

Documents are split into parent chunks (1200 chars) stored in SQLite and child chunks (300 chars) embedded in ChromaDB. At query time, child chunks are matched via cosine similarity, then their corresponding parent chunks are retrieved to provide the LLM with fuller context. This balances retrieval precision with contextual completeness.

## Configuration

Key parameters in [config.py](backend/config.py):

| Parameter | Default | Description |
|-----------|---------|-------------|
| `LLM_MODEL` | `qwen3:8b-q4_K_M` | Ollama model |
| `EMBEDDINGS_MODEL` | `BAAI/bge-large-en-v1.5` | Embedding model |
| `PARENT_CHUNK_SIZE` | 1200 | Parent chunk size (chars) |
| `CHILD_CHUNK_SIZE` | 300 | Child chunk size (chars) |
| `MIN_RELEVANCE_SCORE` | 0.5 | Cosine similarity threshold |
| `OCR_DPI` | 300 | PDF-to-image DPI for OCR |

## Tests

```bash
cd backend
pytest tests/
```

## Notes

- Terrain data is cached in memory (1-hour TTL) to limit redundant API calls.
- Maximum upload size is 50MB.
- The system functions offline once models are downloaded, except for terrain analysis, which requires internet for geographic API access.
