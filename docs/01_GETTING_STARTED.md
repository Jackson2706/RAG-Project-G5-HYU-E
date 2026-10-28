# 01 · Getting Started

This tutorial takes you from a fresh copy of the repository to your first answered question.
It takes about 20 minutes the first time, mostly downloads.

Every command says **which folder to run it from**. `hyu-compass/` means the project root, the
folder that contains `README.md` and `docker-compose.yml`.

You will need **three terminal windows** at the end:

| Terminal | Runs | Keep it open? |
|---|---|---|
| 1 | commands (Docker, ingestion) | no |
| 2 | the backend (FastAPI) | **yes** |
| 3 | the frontend (React) | **yes** |

---

## 1. Prerequisites

Install these once:

| Tool | Why | Check it works |
|---|---|---|
| **Conda** (Miniconda) | manages our Python environment | `conda --version` |
| **Docker Desktop** | runs MongoDB and Qdrant | `docker --version` and `docker compose version` |
| **Ollama** | runs the AI model on your computer | `ollama --version` |
| **Node.js 20+** | runs the frontend | `node --version` and `npm --version` |

On macOS you can install Docker Desktop and Ollama from their websites, and open each app once so
it starts in the background.

## 2. The Conda environment `RAG`

The project uses **one** Python environment called `RAG`. Do not create another environment or
a `venv`. Everyone uses the same one, so "it works on my machine" means the same thing for everyone.

```bash
conda info --envs          # RAG should be in the list
conda activate RAG
python --version           # should print Python 3.13.x
```

✅ **Success looks like:** your prompt starts with `(RAG)`.

If `RAG` is missing, ask the team lead how it was created. Don't make a new one with a
different setup.

## 3. Python dependencies

From `hyu-compass/`:

```bash
conda activate RAG
python -m pip install -r backend/requirements.txt
```

✅ Ends with `Successfully installed …` or only `Requirement already satisfied` lines.

## 4. Start MongoDB and Qdrant (Docker)

The databases need a password. We keep secrets in `.env` files, which git ignores, so you choose
your own.

From `hyu-compass/`:

```bash
cp .env.example .env
cp backend/.env.example backend/.env
```

Open **both** files and replace `change-me-locally` with the same password of your choice. The
`MONGODB_URI` line in `backend/.env` contains the password too.

Then start the databases (from `hyu-compass/`):

```bash
docker compose up -d
docker compose ps
```

✅ **Success looks like:** two services, `mongodb` and `qdrant`, with status `running`
(MongoDB also shows `healthy` after a few seconds).

What just happened:
- **MongoDB** listens on `127.0.0.1:27017` and **Qdrant** on `127.0.0.1:6333`. They are only
  reachable from your own computer.
- Their data is kept in Docker **volumes** (`hyu-compass_mongodb_data`, `hyu-compass_qdrant_data`).
  Stopping the containers keeps the data.

| You want to… | Command (from `hyu-compass/`) |
|---|---|
| stop the databases | `docker compose down` |
| start them again | `docker compose up -d` |
| ⚠️ delete all stored data | `docker compose down -v` (only if you really mean it) |

## 5. Ollama and a model

Ollama runs language models locally. Check it is running and which models you have:

```bash
ollama list
```

If the command fails, start Ollama (open the app, or run `ollama serve` in a spare terminal).
If the list is empty, download a model (≈ 2.5 GB):

```bash
ollama pull qwen3:4b
```

✅ `ollama list` shows `qwen3:4b`.

Tip: set it as the default in `backend/.env` with `OLLAMA_CHAT_MODEL=qwen3:4b`. Otherwise the
first installed model is used. You can always pick another one in the app.

## 6. Add documents and run ingestion

**Ingestion** reads the documents, cuts them into chunks, turns every chunk into a vector and
stores everything in MongoDB and Qdrant. Questions can only be answered after this step.

To practise, use the five sample documents (from `hyu-compass/`):

```bash
conda activate RAG
python scripts/ingest.py --path data/samples
```

✅ **Success looks like:**

```text
Ingesting data/samples (chunk size 256, overlap 32) …
  ✓ samples/course_registration.md           6 chunks  Course Registration Handbook (Sample)
  ✓ samples/erica_housing.md                 5 chunks  ERICA Campus Housing Notice (Sample)
  ✓ samples/orientation_guide.md             6 chunks  New Student Orientation Guide (Sample)
  ✓ samples/scholarships.html                5 chunks  Scholarship Application Guide (Sample)
  ✓ samples/student_services.txt             1 chunks  Student Services Overview (Sample)
Done: 5 documents, 23 chunks, 384-dimensional vectors.
```

The first run downloads the embedding model (~130 MB) and takes longer.

**Your real documents:** copy PDF, TXT, Markdown or HTML files into `data/raw/` (sub-folders are
fine), then run:

```bash
python scripts/ingest.py --path data/raw
```

Ingestion **replaces** the whole index with the folder you give it. You can also change the chunk
settings: `--chunk-size 128 --chunk-overlap 16`.

## 7. Start the backend

In **terminal 2** (stays open), from `hyu-compass/`:

```bash
conda activate RAG
cd backend
python -m uvicorn app.main:app --reload
```

✅ **Success looks like:** `Uvicorn running on http://127.0.0.1:8000` and `Application startup complete`.

Check it in your browser:
- <http://127.0.0.1:8000/api/health> should show `"ok": true` for mongodb, qdrant and ollama.
- <http://127.0.0.1:8000/docs> lists every API endpoint, and you can try them there.

`--reload` restarts the server automatically when you save a Python file.

## 8. Start the frontend

In **terminal 3** (stays open), from `hyu-compass/`:

```bash
cd frontend
npm ci          # first time only (installs the exact package versions from package-lock.json)
npm run dev
```

✅ **Success looks like:** `Local: http://127.0.0.1:5173/`. Open it.

## 9. Ask your first question

1. In the four status dots at the top right, MongoDB, Qdrant, Ollama and Index should be green.
   Open **Configuration → LLM Generation** and pick your model (e.g. `qwen3:4b`).
2. Click the example question **"How many credits can a first-year student register for?"**.
3. Watch the left panel switch to **Execution**: the stages turn green one after another.
4. The answer appears in the chat with a source card such as
   **E1 · Course Registration Handbook (Sample) · Credit Limits**.
5. Click a green stage, for example **Dense Retrieval**, to see its method, real input, output
   and the parameters it used. Grey blocks are future methods: see [05_ADD_NEW_METHOD.md](05_ADD_NEW_METHOD.md).

Then try a question the documents can't answer, such as *"Where can I park my car?"*. The app should
say it could not find enough information instead of guessing.

## 10. Run the tests

From `hyu-compass/`:

```bash
conda activate RAG
cd backend && python -m pytest          # backend tests (no Docker or Ollama needed)
cd ../frontend && npm test && npm run build
```

✅ Every test reports `passed` and the build ends with `✓ built in …`.

## 11. Common errors and fixes

| What you see | Why | Fix |
|---|---|---|
| `docker: command not found` | Docker Desktop is not installed or not running | Install/open Docker Desktop |
| `set MONGO_ROOT_USERNAME in .env` | `.env` is missing | `cp .env.example .env` (from `hyu-compass/`) |
| `/api/health` → mongodb `Authentication failed` | passwords in `.env` and `backend/.env` differ | make them equal. If you changed the password *after* the first `docker compose up`, the old one is still stored in the volume: use the old one, or reset with `docker compose down -v` (deletes data) |
| `/api/health` → mongodb or qdrant `Connection refused` | databases not started | `docker compose up -d` |
| Chat: *"No documents are indexed yet"* | ingestion has not been run | `python scripts/ingest.py --path data/samples` |
| Chat: *"Cannot reach Ollama"* | Ollama is not running | open the Ollama app or run `ollama serve` |
| Chat: *"No Ollama models are installed"* | no model downloaded | `ollama pull qwen3:4b` |
| Chat: *"The model used all 'Max generated tokens' before answering"* | thinking models (qwen3) spend tokens on hidden reasoning | Configuration tab → **LLM Generation** → **Max generated tokens** → 2048 |
| UI: *"Cannot reach the backend"* | backend not running | start it (step 7) |
| `ModuleNotFoundError: No module named 'app'` | uvicorn started from the wrong folder | run it from `hyu-compass/backend/` |
| `ModuleNotFoundError` for fastapi, qdrant_client, … | wrong Python environment | `conda activate RAG` |
| Port 8000/5173 already in use | an old server is still running | close the other terminal, or stop it with Ctrl+C |
| Embedding model download fails | no internet on first run | connect once; afterwards it is cached |

### Running without Docker (fallback)

Qdrant can run inside the backend process: set `QDRANT_PATH=qdrant_data` in `backend/.env` (the
folder is created inside `backend/`). Only one program can open that folder at a time, so stop the
backend before running `scripts/ingest.py`, or re-index from the app's Configuration tab (Ingestion section) instead.
MongoDB still needs Docker (or a local MongoDB installation).
