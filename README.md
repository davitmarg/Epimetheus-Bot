# Project Epimetheus: Slack-to-Docs RAG Bot

Epimetheus listens to Slack conversations, extracts new knowledge, and keeps Google Docs up to date. It uses RAG (ChromaDB + LLM) to route updates to the right document and stores version history in MongoDB.

## Components
- Bot Listener (`services/bot/entry.py`): socket-mode Slack bot that buffers messages per thread and pushes batches to Redis.
- Updater Service (`services/updater_service/entry.py`): Redis consumer that chunks messages, extracts knowledge, decides whether to update, writes to Google Docs, stores versions, updates vectors, and optionally notifies Slack.
- API Service (`services/api_service/entry.py` + `services/api_service/routes.py`): FastAPI app for manual operations (list/search documents, sync Drive mapping, manage versions, health).
- Repository layer:
  - `repository/drive_repository.py`: Google Drive/Docs operations.
  - `repository/document_repository.py`: MongoDB metadata + versions, vector search, queue consumption, orchestration helpers.
  - `repository/llm_repository/*`: LLM prompts, document update generation, agent tools.
  - `repository/slack_repository.py`: Slack notifications.
- Shared utilities: `utils/db_utils.py` (Redis/Mongo/Chroma), `utils/message_utils.py`, `utils/logger.py`, `utils/constants.py`.

## Data Flow
1. Slack event -> Bot Listener buffers per thread -> pushes to Redis queue `epimetheus:updater_queue`.
2. Updater Service consumes queue:
   - chunk messages, extract knowledge with LLM,
   - choose target doc via Chroma similarity + metadata,
   - read current doc from Google Docs,
   - generate new content + change summary,
   - save version to Mongo, write partial update to Google Docs, refresh vectors, optionally notify Slack.
3. API Service exposes manual controls (mapping sync, document CRUD, version browse/revert, health).

## Running the services
### With Docker Compose
```bash
cp .env-example .env   # fill in tokens/keys/IDs
docker-compose up -d
```
Starts Redis, MongoDB, ChromaDB, and the Epimetheus app (bot + updater + API).

### Locally (without Docker)
```bash
pip install -r requirements.txt
cp .env-example .env   # fill in Slack, Google, OpenAI, DB config
python main.py         # runs bot + updater (thread) + API
```
Run individually:
```bash
python main.py bot
python main.py updater
python main.py api
```

## Configuration (env vars)
- `SLACK_BOT_TOKEN`, `SLACK_APP_TOKEN` (socket mode).
- `GOOGLE_CREDENTIALS_PATH` (service account JSON), `GOOGLE_DRIVE_FOLDER_ID`.
- `OPENAI_API_KEY`, `OPENAI_BASE_URL` (optional), `OPENAI_MODEL` (default `gpt-4`).
- Redis: `REDIS_HOST`, `REDIS_PORT`, `REDIS_DB`.
- MongoDB: `MONGODB_HOST`, `MONGODB_PORT`, `MONGODB_DATABASE`, `MONGODB_USERNAME`, `MONGODB_PASSWORD`, `MONGODB_URI` (optional override).
- ChromaDB: `CHROMA_DB_PATH`, `CHROMA_HOST`, `CHROMA_PORT`, `CHROMA_USE_HTTP`.
- Tuning: `MESSAGE_CHUNK_SIZE`, `KNOWLEDGE_EXTRACTION_THRESHOLD`.

Place the Google service account JSON in the project root (or point `GOOGLE_CREDENTIALS_PATH` to it) and share the target Drive folder with the service account email.

## API overview (FastAPI)
Base URL defaults to `http://localhost:8000`.
- `GET /health` – service health.
- `GET /api/v1/status` – API status message.
- Documents: `GET /api/v1/documents`, `GET /api/v1/documents/search`, `POST /api/v1/documents`, `GET /api/v1/documents/{doc_id}`, `GET /api/v1/documents/{doc_id}/metadata`, `PUT /api/v1/documents/{doc_id}/metadata`, `GET /api/v1/documents/metadata/all`.
- Drive mapping: `GET /api/v1/drive/mapping`, `POST /api/v1/drive/mapping/sync`, `PUT /api/v1/drive/mapping/document`.
- Versions: `GET /api/v1/versions/{doc_id}`, `GET /api/v1/versions/{doc_id}/{version_id}`, `POST /api/v1/revert/{doc_id}/{version_id}`.
- Trigger check: `POST /api/v1/trigger` (verifies a doc exists; processing is otherwise automatic).

## Project structure
```
Epimetheus-Bot/
├── main.py
├── services/
│   ├── bot/                    # Slack bot
│   │   ├── app.py
│   │   ├── buffer.py
│   │   ├── entry.py
│   │   ├── handlers.py
│   │   └── ui.py
│   ├── updater_service/        # Redis consumer + update orchestration
│   │   ├── core.py
│   │   ├── entry.py
│   │   ├── intelligence.py
│   │   └── storage.py
│   └── api_service/            # FastAPI service
│       ├── __init__.py
│       ├── entry.py
│       ├── routes.py
│       └── schemas.py
├── repository/
│   ├── drive_repository.py
│   ├── document_repository.py
│   ├── slack_repository.py
│   └── llm_repository/
│       ├── agentic.py
│       ├── core.py
│       ├── prompts.py
│       └── __init__.py
├── utils/
│   ├── constants.py
│   ├── db_utils.py
│   ├── logger.py
│   └── message_utils.py
├── tests/
│   ├── conftest.py
│   └── test_integration_drive_and_document_repo.py
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── .env-example
└── README.md
```

## Testing
Integration tests rely on real Google and Mongo connections; set the env vars then run:
```bash
pytest tests/ -v
```

## Notes
- The updater uses both direct calls (from the agent) and the Redis queue for log-style processing.
- Drive mapping is synced automatically on startup via the updater/API; `/api/v1/drive/mapping/sync` is available for manual runs.
- Version history is stored in MongoDB and can be reverted via the API.
