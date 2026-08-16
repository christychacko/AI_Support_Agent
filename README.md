# AI Support Agent (Production-Grade, Free-Tier Stack)

An end-to-end customer support agent:

```
User → FastAPI (streaming) → LangGraph Router
                                 ├── RAG (Chroma, local, free embeddings)
                                 ├── Order Tool (MCP server, SQLite)
                                 ├── Ticket Tool (MCP server, SQLite)
                                 └── Human Escalation (mock webhook)
                              → Structured Pydantic response
```

Everything below uses **free / open-source / free-tier** services so you can run
the whole thing on your laptop for $0, then deploy to Cloud Run's free tier.

---

## 1. Why each piece exists (read this first)

| Requirement | Tool used | Why it's free |
|---|---|---|
| Orchestration | **LangGraph** | open source |
| Tool protocol | **MCP** (Model Context Protocol) via `mcp` SDK + `langchain-mcp-adapters` | open source |
| Memory | LangGraph **SqliteSaver** checkpointer | local file, $0 |
| Structured output | **Pydantic v2** | open source |
| RAG | **Chroma** (local vector DB) + `sentence-transformers` embeddings | runs on your CPU, no API cost |
| Primary LLM | **Groq** (Llama 3.1) or **Ollama** (local) | generous free tier / fully offline |
| Fallback LLM | **Ollama** (local) or a second Groq model | fully free / offline |
| Tracing | **Langfuse** (self-hosted via Docker) | open source |
| Metrics | **Prometheus + Grafana** (self-hosted via Docker) | open source |
| API | **FastAPI** with SSE streaming | open source |
| CI/CD | **GitHub Actions** | free for public repos / 2000 min/mo private |
| Hosting | **GCP Cloud Run** | free tier: 2M requests/month |
| Observability plumbing | **OpenTelemetry** | open source, vendor-neutral |

You only need **one** API key to start: a free Groq key from https://console.groq.com

---

## 2. Project layout

```
ai-support-agent/
├── app/
│   ├── main.py               # FastAPI app, /chat streaming endpoint, /metrics
│   ├── config.py              # env-based settings
│   ├── schemas.py             # Pydantic I/O contracts
│   ├── graph/
│   │   ├── state.py           # LangGraph shared state
│   │   ├── llm.py             # primary+fallback model wrapper (with retry)
│   │   ├── router.py          # classifies intent -> structured RouteDecision
│   │   ├── nodes.py           # RAG / order / ticket / escalation graph nodes
│   │   └── build_graph.py     # wires the StateGraph together
│   ├── tools/
│   │   ├── rag_tool.py        # Chroma retriever
│   │   ├── mcp_client.py      # connects to the MCP server over stdio
│   ├── memory/
│   │   └── checkpointer.py    # SQLite-backed conversation memory
│   ├── observability/
│   │   ├── tracing.py         # OpenTelemetry + Langfuse setup
│   │   └── metrics.py         # Prometheus counters/histograms
│   └── data/knowledge_base/   # sample support docs for RAG
├── mcp_server/server.py       # MCP server exposing order_lookup + create_ticket
├── scripts/ingest_kb.py       # builds the Chroma index from knowledge_base/
├── tests/test_graph.py        # smoke tests
├── docker/Dockerfile
├── docker-compose.yml         # app + prometheus + grafana + langfuse
├── prometheus.yml
├── .github/workflows/deploy.yml
├── requirements.txt
├── .env.example
└── cloudrun-deploy.md
```

---

## 3. Run it locally

```bash
cd ai-support-agent
# edit .env and paste your free Groq key: GROQ_API_KEY=gsk_...

python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 1. Build the RAG index from the sample docs
python scripts/ingest_kb.py

# 2. Start everything (app + prometheus + grafana)
docker compose up --build
```

Then:
- API docs: http://localhost:8000/docs
- Stream a chat: `POST http://localhost:8000/chat` (see below)
- Prometheus: http://localhost:9090
- Grafana: http://localhost:3000 (admin/admin)

### Try it without Docker (pure Python, fastest for beginners)
```bash
uvicorn app.main:app --reload
```

### Example request
```bash
curl -N -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"user_id":"u1","session_id":"s1","message":"Where is my order #1002?"}'
```
You'll get back a Server-Sent-Events stream ending in one structured JSON
object validated against `AgentResponse` (see `app/schemas.py`).

---

## 4. How the graph works

1. **Router node** — the LLM classifies the message into one of
   `knowledge_question | order_status | complaint | human_needed`, returned as
   a structured Pydantic `RouteDecision` (no regex/keyword guessing).
2. Based on that decision, LangGraph conditionally routes to:
   - **RAG node** — retrieves top-k chunks from Chroma, answers with citations.
   - **Order tool node** — calls the MCP `order_lookup` tool (SQLite-backed).
   - **Ticket tool node** — calls the MCP `create_ticket` tool.
   - **Escalation node** — creates a human-handoff record + (optional) webhook.
3. Every path converges on a **finalize node** that formats an `AgentResponse`
   Pydantic object — this is what's guaranteed to leave the graph.
4. **Memory**: each `session_id` is a LangGraph *thread*. The `SqliteSaver`
   checkpointer persists full state (including message history) between
   requests, so the same session remembers prior turns for free.
5. **Fallback model**: `app/graph/llm.py` wraps a primary Groq call; on
   timeout/rate-limit/5xx it retries against a fallback model automatically.

---

## 5. Using Ollama instead of (or alongside) Groq

`app/graph/llm.py` treats the model provider as a config value, not a
hardcoded choice. `PRIMARY_PROVIDER` / `FALLBACK_PROVIDER` in `.env` can each
independently be `groq` or `ollama` — see the three options already laid out
in `.env.example`.

**Local setup:**
```bash
# install Ollama: https://ollama.com/download
ollama serve                 # starts the local server on :11434
ollama pull llama3.1         # ~4.7GB, one-time download
ollama pull llama3.2:3b      # optional smaller/faster model for the fallback slot
```

Then in `.env`:
```bash
# fully offline, zero API keys, zero cost
PRIMARY_PROVIDER=ollama
PRIMARY_MODEL=llama3.1
FALLBACK_PROVIDER=ollama
FALLBACK_MODEL=llama3.2:3b
OLLAMA_BASE_URL=http://localhost:11434
```

Or keep Groq's speed for normal traffic and use Ollama only as a free local
safety net when Groq rate-limits you:
```bash
PRIMARY_PROVIDER=groq
PRIMARY_MODEL=llama-3.1-70b-versatile
GROQ_API_KEY=gsk_...
FALLBACK_PROVIDER=ollama
FALLBACK_MODEL=llama3.1
```

**Running via Docker Compose:** uncomment the `ollama` service in
`docker-compose.yml`, set `OLLAMA_BASE_URL=http://ollama:11434` in `.env`
(the container hostname, not `localhost`), then after `docker compose up`
pull a model once with `docker compose exec ollama ollama pull llama3.1`.

**Caveats:**
- Ollama's structured-output support (used by the router/RAG nodes via
  `.with_structured_output()`) works well with newer models like
  `llama3.1`/`llama3.2` but is less reliable on older/smaller models —
  stick to 3B+ instruction-tuned models for the router.
- Local inference is CPU/GPU-bound by your machine; expect it to be slower
  than Groq unless you have a decent GPU.
- On Cloud Run, Ollama isn't practical (no persistent GPU, cold starts) —
  use Groq (or another hosted free-tier API) for the deployed version, and
  Ollama for local dev if you want $0 iteration.

## 6. Deploying to Cloud Run (free tier)

See `cloudrun-deploy.md` for the full walkthrough. Short version:

```bash
gcloud auth login
gcloud config set project YOUR_PROJECT_ID
gcloud services enable run.googleapis.com artifactregistry.googleapis.com

gcloud artifacts repositories create support-agent --repository-format=docker --location=us-central1

gcloud builds submit --tag us-central1-docker.pkg.dev/YOUR_PROJECT_ID/support-agent/api

gcloud run deploy support-agent \
  --image us-central1-docker.pkg.dev/YOUR_PROJECT_ID/support-agent/api \
  --region us-central1 --allow-unauthenticated \
  --set-env-vars GROQ_API_KEY=your_key
```

`.github/workflows/deploy.yml` automates exactly this on every push to `main`
(you just add `GCP_SA_KEY` and `GCP_PROJECT_ID` as GitHub Secrets).

---

