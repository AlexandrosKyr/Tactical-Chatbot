# Tactical Intelligence

An AI-powered terrain analysis assistant that performs Intelligence Preparation of the Battlefield (IPB) using real geographic data. It follows widely available NATO methodology and given a set of coordinates, it pulls actual infrastructure, elevation, and weather data from open geographic APIs and produces a structured IPB assessment covering terrain analysis (OAKOC), civil considerations (ASCOPE), threat evaluation, and enemy course of action development.

The system also supports document ingestion with OCR, so doctrine manuals and reference material can be indexed and retrieved during analysis through a RAG pipeline.

Everything runs locally. The LLM runs on-device through Ollama, and no data leaves the machine except for geographic API queries.

## What the System Produces

When given coordinates, the assistant generates a full IPB output:

1. **Situation Overview** - tactical context and data quality notes
2. **Terrain Analysis (IPB Step 2 - OAKOC)** - Observation & Fields of Fire, Avenues of Approach, Key Terrain, Obstacles, Cover & Concealment
3. **Civil Considerations (ASCOPE)** - sensitive sites, infrastructure, population impact
4. **Threat Evaluation (IPB Step 3)** - assessed enemy composition, TTPs, capabilities in the terrain
5. **Enemy Courses of Action (IPB Step 4)** - Most Probable COA, Most Dangerous COA, decision points
6. **Named Areas of Interest** - collection priorities with indicator analysis
7. **Recommendations** - actionable items for the commander

The terrain data behind this is real - roads, waterways, bridges, railways, forests, buildings, elevation profiles, slope gradients, and weekly weather, all pulled from OpenStreetMap and Open-Meteo at query time.

## Scenario Detection

The system detects the operational context from the user's message and tailors its analysis accordingly:

- **Defensive** - engagement areas, obstacle integration, key terrain to retain
- **Offensive** - avenues of approach, objectives, breach/bypass considerations
- **Stability** - civil considerations, sensitive sites, critical infrastructure
- **Reconnaissance** - observation positions, NAIs, screen lines, collection priorities

## Document Processing

PDFs and images can be uploaded as reference material (doctrine, field manuals, orders). The system extracts text using direct parsing or OCR, splits it into hierarchical chunks, and indexes everything into a vector database. During analysis, relevant passages are retrieved and cited with the source document and page number.

Supports a permanent knowledge base (always available) and session uploads (temporary).

## Tech Stack

| Layer | Technology |
|-------|------------|
| Frontend | React 19, Tailwind CSS |
| Backend | Python 3.12+ / Flask |
| LLM | Ollama (qwen3:8b-q4_K_M, local inference) |
| Embeddings | BAAI/bge-large-en-v1.5 via HuggingFace |
| Vector DB | ChromaDB (persistent) |
| Parent Store | SQLite (hierarchical chunk resolution) |
| OCR | Tesseract |
| Geographic APIs | OpenStreetMap Overpass, Open-Meteo (elevation + weather) |

## Prerequisites

- Python 3.12+
- Node.js
- Ollama is installed and running
- Tesseract OCR installed (`brew install tesseract` on macOS)

## Setup

**Backend:**

```bash
cd backend
pip install -r requirements.txt
```

Create `backend/.env`:

```
OLLAMA_HOST=http://localhost:11434
```

```bash
python app.py
```

**Frontend:**

```bash
npm install
npm start
```

**LLM model:**

```bash
ollama pull qwen3:8b-q4_K_M
```

## How Retrieval Works

Documents are split into parent chunks (1200 chars, stored in SQLite) and child chunks (300 chars, embedded in ChromaDB). At query time, child chunks are matched by cosine similarity, then their parent chunks are retrieved to give the LLM fuller context. During terrain analysis, the retrieval query is enhanced with terrain-derived keywords (e.g., "urban operations" if the area has dense buildings, "water obstacle river crossing" if waterways are present) to improve doctrine matching.

## Terrain Data Collected

For each coordinate query, the system fetches:

- **Roads** - classified by type (motorway through track), named routes
- **Waterways** - rivers, streams, canals with deduplication into distinct features
- **Crossings** - bridges, fords, tunnels, dams with capacity assessment
- **Railways** - as linear obstacles
- **Elevation** - center point + 8 cardinal/diagonal sample points, slope computation
- **Forests** - cover/concealment areas, named and unnamed
- **Buildings** - urban density assessment
- **Tactical infrastructure** - power lines, cell towers, fuel stations, helipads
- **Sensitive sites** - hospitals, clinics, schools, universities (ROE considerations)
- **Weather** - 7-day history with tactical impact assessment
- **Movement estimates** - time-distance calculations for infantry, wheeled, and tracked vehicles adjusted for terrain modifiers

## Configuration

Key parameters in [config.py](backend/config.py):

| Parameter | Default | Purpose |
|-----------|---------|---------|
| `LLM_MODEL` | `qwen3:8b-q4_K_M` | Ollama model for analysis |
| `EMBEDDINGS_MODEL` | `BAAI/bge-large-en-v1.5` | Embedding model for retrieval |
| `PARENT_CHUNK_SIZE` | 1200 | Parent chunk size in characters |
| `CHILD_CHUNK_SIZE` | 300 | Child chunk size in characters |
| `MIN_RELEVANCE_SCORE` | 0.5 | Cosine similarity threshold |

## Notes

- Terrain data is cached in memory with a 1-hour TTL to avoid redundant API calls for the same area.
- Maximum upload size is 50MB.
- The system works offline once models are pulled, except for terrain analysis, which needs network access for geographic APIs.
- Conversation context is maintained across turns - follow-up questions reuse the last analysed terrain data without re-fetching.
