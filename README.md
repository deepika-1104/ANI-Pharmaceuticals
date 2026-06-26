# ANI Pharmaceuticals — Voxa AI Platform
 
An AI-powered plant operations platform for ANI Pharmaceuticals. Voxa is a voice-and-chat assistant connected to live plant data, backed by a FastAPI + MongoDB backend and a React/Vite frontend with multi-domain dashboards.
 
---
 
## Features
 
### AI Assistant (Voxa)
- **LLM-powered chat** scoped to the active domain (Production or Quality)
- **Voice input** via Whisper-compatible speech-to-text
- **Strict data grounding** — all answers are sourced exclusively from live plant data; no hallucinations
- **Provider-agnostic LLM** — switch between Groq, OpenAI, Together, DeepSeek, Anthropic, Gemini, Ollama, or Azure via a single env variable
- **RAG** (Retrieval-Augmented Generation) for uploaded documents
- **Vision support** — image understanding when a compatible vision model is configured
 
### Dashboards
The frontend provides five domain dashboards, each with AI chat context scoped to that domain:
 
| Domain | Description |
|---|---|
| **Enterprise Overview** | Cross-domain KPIs (production output, packaging efficiency, quality pass rate, on-time delivery), weekly performance trends, radar chart |
| **Production Overview** | Live batch tracking, area-wise output (granulation, compression, coating, packaging), equipment parameters, alert counts, shift activity |
| **Packaging Overview** | Line efficiency, package counts, packaging-specific metrics |
| **Quality Overview** | Batch inspection results, NCR/CAPA tracking, audit scores, upcoming audit schedules |
| **Logistics Overview** | On-time delivery rate, in-transit shipment tracking |
 
### Backend
- **Query orchestrator** — multi-step pipeline: intent classification → collection selection → semantic expansion → query normalisation → context building → analytics execution → follow-up engine
- **Dashboard API** — `/api/production-dashboard/summary` and `/api/quality-dashboard/summary` return aggregated metrics (today, yesterday, last 9 days, shift data, parameter ranges)
- **Automatic data ingestion** — CSV/JSON files in `data/` are loaded into MongoDB on startup (idempotent)
- **Response cache** — identical queries served from an in-process cache (default 4-hour TTL)
- **JWT auth** — access token (60 min) + refresh token (1 day / 30 days with "remember me")
- **Full async** — Motor (async MongoDB driver) + uvicorn
 
---
 
## Project Structure
 
```
ANI-Pharmaceuticals/
├── backend/
│   ├── main.py                   # FastAPI app entry point
│   ├── config/settings.py        # All env-var based configuration
│   ├── routers/
│   │   ├── auth.py               # Login, signup, refresh
│   │   ├── chat.py               # Streaming chat endpoint
│   │   ├── dashboard.py          # Production & quality dashboard APIs
│   │   ├── documents.py          # RAG document upload/management
│   │   ├── health.py
│   │   ├── history.py
│   │   ├── query.py
│   │   └── speech.py             # STT transcription
│   ├── orchestrator/
│   │   ├── query_orchestrator.py # Main pipeline coordinator
│   │   ├── intent_classifier.py
│   │   ├── collection_selector.py
│   │   ├── semantic_expander.py
│   │   ├── query_normalizer.py
│   │   ├── context_builder.py
│   │   ├── analytics_executor.py
│   │   └── followup_engine.py
│   ├── data_ingestion/loader.py  # CSV/JSON → MongoDB ingestion
│   ├── prompts/
│   │   ├── builder.py
│   │   └── intents.py
│   ├── rag/                      # Document chunking & retrieval
│   ├── database/mongodb.py
│   ├── models/
│   ├── services/
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.jsx               # Root — routing, auth guard, theme
│   │   ├── pages/
│   │   │   ├── Landing.jsx       # Login / signup
│   │   │   ├── PharmaAIPage.jsx  # Main app shell with domain sidebar
│   │   │   ├── PharmaPlantDashboard.jsx  # Production dashboard
│   │   │   └── Dashboard.jsx
│   │   ├── components/
│   │   │   ├── ai/
│   │   │   │   ├── AIHeader.jsx
│   │   │   │   ├── EnterpriseDashboard.jsx
│   │   │   │   ├── QualityDashboard.jsx
│   │   │   │   ├── PackagingDashboard.jsx
│   │   │   │   ├── LogisticsDashboard.jsx
│   │   │   │   ├── DomainSelector.jsx
│   │   │   │   └── WelcomeHero.jsx
│   │   │   ├── ChatWindow.jsx
│   │   │   ├── Sidebar.jsx
│   │   │   └── VoiceButton.jsx
│   │   ├── hooks/
│   │   │   ├── useProductionData.js  # Fetches /api/production-dashboard/summary
│   │   │   └── useQualityData.js     # Fetches /api/quality-dashboard/summary
│   │   ├── store/
│   │   │   ├── useChatStore.js
│   │   │   ├── useAuthStore.js
│   │   │   └── useThemeStore.js
│   │   └── services/api.js
├── data/                         # CSV/JSON files auto-ingested on startup
├── render.yaml                   # Render deployment config
├── start.bat / start.sh          # Local dev launchers
└── runtime.txt
```
 
---
 
## Getting Started
 
### Prerequisites
- Python 3.10+
- Node.js 18+
- MongoDB Atlas URI (or local MongoDB)
- LLM API key (Groq recommended as default)
 
### Backend
 
```bash
cd backend
cp .env.example .env   # fill in required values (see Environment Variables)
pip install -r requirements.txt
python main.py
```
 
The API will be available at `http://localhost:8000`. Swagger docs at `/docs`.
 
### Frontend
 
```bash
cd frontend
npm install
# Create .env.local with:
# VITE_API_URL=http://localhost:8000/api
npm run dev
```
 
The app will be available at `http://localhost:5173`.
 
### Quick Start (Windows)
 
```bat
start.bat
```
 
---
 
## Environment Variables
 
Create `backend/.env`:
 
```env
# LLM — required
LLM_PROVIDER=groq           # groq | openai | anthropic | gemini | together | deepseek | ollama | azure
LLM_API_KEY=your_key_here
PRIMARY_MODEL=llama-3.3-70b-versatile
FALLBACK_MODEL=llama-3.1-8b-instant
 
# MongoDB — required
MONGO_URI=mongodb+srv://...
MONGO_DB_NAME=voxa
 
# Auth — required in production
JWT_SECRET=change-this-to-a-long-random-secret
REFRESH_TOKEN_SECRET=change-this-too
 
# Optional
CORS_ORIGINS=https://your-frontend.onrender.com
DATA_DIR=../data              # directory scanned for CSV/JSON to ingest
ASSISTANT_NAME=Voxa
RESPONSE_CACHE_TTL=14400      # seconds; 0 to disable
 
# Optional — vector search
EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_API_KEY=...
 
# Optional — vision
VISION_MODEL=meta-llama/llama-4-scout-17b-16e-instruct
 
# Optional — file storage (Supabase)
STORAGE_BACKEND=local         # local | supabase
SUPABASE_URL=...
SUPABASE_SERVICE_ROLE_KEY=...
```
 
---
 
## Data Ingestion
 
Place CSV or JSON files in the `data/` directory. On every startup the backend scans this directory and loads each file into a MongoDB collection named after the file (e.g. `production_dashboard.csv` → `production_dashboard` collection). Ingestion is idempotent — collections with existing documents are skipped.
 
Internal collections (`users`, `chats`, `sessions`, `rag_chunks`) are never overwritten.
 
---
 
## API Overview
 
| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/health` | Health check |
| `POST` | `/api/auth/login` | Login, returns JWT + refresh token |
| `POST` | `/api/auth/signup` | Register |
| `POST` | `/api/auth/refresh` | Refresh access token |
| `POST` | `/api/chat` | Streaming AI chat |
| `GET` | `/api/production-dashboard/summary` | Aggregated production metrics |
| `GET` | `/api/quality-dashboard/summary` | Aggregated quality metrics |
| `POST` | `/api/speech/transcribe` | Audio → text (STT) |
| `GET/POST` | `/api/documents` | RAG document management |
| `GET` | `/api/history` | Conversation history |
 
---
 
## Deployment
 
The project includes a `render.yaml` for one-command deployment to [Render](https://render.com):
 
- **Backend** — Python web service, builds with `pip install -r requirements.txt`
- **Frontend** — Static site, builds with `npm ci && npm run build`, served from `dist/`
 
Set the secret env vars (`LLM_API_KEY`, `MONGO_URI`, `JWT_SECRET`, etc.) in the Render dashboard.
 
---
 
## Tech Stack
 
**Backend**
- Python 3.10+, FastAPI, uvicorn
- Motor (async MongoDB driver)
- python-jose (JWT)
- openai-compatible SDK (provider-agnostic LLM calls)
 
**Frontend**
- React 18, Vite
- Tailwind CSS
- Recharts (bar, line, radar charts)
- React Router v6
- Zustand (state management)
- react-hot-toast
 
---
 
## License
 
See [LICENSE](LICENSE).