# Repo Sync

Load Odoo modules from a GitHub organization into a Qdrant vector database and expose them via a FastAPI search API for an OpenAI Custom GPT.

## Architecture

```
GitHub Org Repos --> [GitHub Actions / Self-hosted Runner]
                          |
                          v
                    +-------------+
                    | Sync Pipeline|  (clone repos -> detect modules -> parse -> embed -> upsert)
                    +------+------+
                           |
                    +------v------+
                    |    Qdrant    |  3 collections: odoo_code, odoo_manifests, odoo_views
                    +------+------+
                           |
                    +------v------+
                    |  FastAPI     |  /search/code, /search/views, /search/manifests, /docs/generate
                    +------+------+
                           |
                    +------v------+
                    | OpenAI GPT  |  Custom GPT via Actions (OpenAPI spec)
                    +-------------+
```

## Quick Start

### Prerequisites

- Python 3.11+
- Docker (for Qdrant)
- GitHub personal access token with org read access
- OpenAI API key

### Setup

1. Clone and install:
   ```bash
   git clone <repo-url> repo_sync
   cd repo_sync
   pip install .
   ```

2. Configure environment:
   ```bash
   cp .env.example .env
   # Edit .env with your tokens
   ```

3. Start Qdrant:
   ```bash
   docker compose up -d qdrant
   ```

4. Run sync:
   ```bash
   repo-sync
   ```

5. Start the API:
   ```bash
   repo-sync-api
   ```

## Configuration

All settings are configured via environment variables or a `.env` file:

| Variable | Description | Default |
|---|---|---|
| `GITHUB_TOKEN` | GitHub personal access token | (required) |
| `GITHUB_ORG_NAME` | GitHub organization name | (required) |
| `OPENAI_API_KEY` | OpenAI API key | (required) |
| `OPENAI_EMBEDDING_MODEL` | Embedding model | `text-embedding-3-small` |
| `OPENAI_CHAT_MODEL` | Chat model for doc generation | `gpt-4o-mini` |
| `QDRANT_URL` | Qdrant server URL | `http://localhost:6333` |
| `QDRANT_API_KEY` | Qdrant API key (if auth enabled) | |
| `REPOS_DIR` | Directory to clone repos into | `./repos` |
| `SYNC_STATE_PATH` | Path to sync state JSON | `./sync_state.json` |
| `API_HOST` | API server host | `0.0.0.0` |
| `API_PORT` | API server port | `8000` |

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/search/code` | Search Python code chunks |
| `POST` | `/search/views` | Search XML views and templates |
| `POST` | `/search/manifests` | Search module manifests |
| `POST` | `/search/all` | Search across all collections |
| `POST` | `/docs/generate` | Generate module documentation |
| `GET` | `/health` | Health check + collection stats |

### Example: Search Code

```bash
curl -X POST http://localhost:8000/search/code \
  -H "Content-Type: application/json" \
  -d '{"query": "compute method for sale order total", "limit": 5}'
```

### Example: Generate Docs

```bash
curl -X POST http://localhost:8000/docs/generate \
  -H "Content-Type: application/json" \
  -d '{"module_name": "sale_custom"}'
```

## Qdrant Collections

| Collection | Content | Key Filters |
|---|---|---|
| `odoo_code` | Python source chunks | repo_name, module_name, chunk_type, file_path |
| `odoo_manifests` | Module manifests | repo_name, module_name, module_category |
| `odoo_views` | XML views, QWeb templates | repo_name, module_name, xml_id, view_type, view_model |

## Docker Compose

Run both Qdrant and the API server:

```bash
docker compose up -d
```

## GitHub Actions

The sync workflow runs every 6 hours on a self-hosted runner. Configure secrets:

- `ORG_GITHUB_TOKEN` - GitHub token with org access
- `GITHUB_ORG_NAME` - Organization name
- `OPENAI_API_KEY` - OpenAI API key

Trigger manually via `workflow_dispatch` in the Actions tab.

## Incremental Sync

The sync pipeline tracks the last-synced commit SHA per repository. On each run:

1. Compares HEAD SHA vs stored SHA
2. Skips repos that haven't changed
3. For changed repos, identifies affected files via `git diff`
4. Only re-indexes modules containing changes
5. Deletes old points and re-inserts (avoids stale data)

## OpenAI Custom GPT

The API serves an OpenAPI spec at `/openapi.json` that can be imported directly into OpenAI GPT Actions. CORS is configured for `chat.openai.com` and `chatgpt.com`.
