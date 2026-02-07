# Plan: Load Odoo Modules from GitHub into Qdrant Vector Database

## Context

The project `repo_sync` is a brand new, empty repository. The goal is to build a system that:
1. Clones all repositories from a GitHub organization
2. Detects Odoo modules within each repo (by `__manifest__.py`)
3. Parses and chunks all module content (Python, XML, manifests, JS, CSS)
4. Embeds chunks using OpenAI `text-embedding-3-small` (1536 dims)
5. Stores vectors in a local Qdrant instance (Docker, localhost:6333)
6. Exposes a FastAPI search/doc-generation API consumed by an OpenAI Custom GPT
7. Sync is triggered by GitHub Actions on a self-hosted runner

## Architecture Overview

```
GitHub Org Repos ──> [GitHub Actions / Self-hosted Runner]
                          │
                          ▼
                    ┌───────────────┐
                    │ Sync Pipeline │  (clone repos → detect modules → parse → embed → upsert)
                    └───────┬───────┘
                            │
                    ┌───────▼──────┐
                    │    Qdrant    │  3 collections: odoo_code, odoo_manifests, odoo_views
                    └───────┬──────┘
                            │
                    ┌───────▼──────┐
                    │    FastAPI   │  /search/code, /search/views, /search/manifests, /docs/generate
                    └───────┬──────┘
                            │
                    ┌───────▼──────┐
                    │  OpenAI GPT  │  Custom GPT via Actions (OpenAPI spec)
                    └──────────────┘
```

## Project Structure

```
repo_sync/
├── .env.example
├── .github/workflows/sync.yml
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
├── README.md
├── src/repo_sync/
│   ├── __init__.py
│   ├── config.py                  # Pydantic Settings from .env
│   ├── models.py                  # ContentChunk, OdooModule, enums
│   ├── sync/
│   │   ├── __init__.py
│   │   ├── cli.py                 # CLI entry point: `repo-sync`
│   │   ├── github_client.py       # Org repo listing, clone/pull
│   │   ├── odoo_discovery.py      # Walk repos, detect modules by __manifest__.py
│   │   ├── embeddings.py          # OpenAI batch embedding with tiktoken
│   │   ├── qdrant_loader.py       # Collection management, upsert, delete
│   │   ├── state.py               # Incremental sync state (JSON)
│   │   ├── pipeline.py            # Orchestrates the full sync workflow
│   │   └── parsers/
│   │       ├── __init__.py
│   │       ├── manifest_parser.py # __manifest__.py → single structured chunk
│   │       ├── python_parser.py   # AST-based: classes, functions, module-level
│   │       ├── xml_parser.py      # lxml-based: records, templates, menus
│   │       └── generic_parser.py  # Line-based chunking for JS/CSS/other
│   └── api/
│       ├── __init__.py
│       ├── app.py                 # FastAPI app factory + uvicorn runner
│       ├── dependencies.py        # Shared DI (Qdrant client, OpenAI, Settings)
│       ├── schemas.py             # Request/response Pydantic models
│       └── routers/
│           ├── __init__.py
│           ├── search.py          # POST /search/code, /search/views, /search/manifests, /search/all
│           ├── docs.py            # POST /docs/generate
│           └── health.py          # GET /health
└── tests/
    ├── __init__.py
    ├── conftest.py
    ├── test_parsers/
    ├── test_sync/
    └── test_api/
```

## Key Dependencies (pyproject.toml)

- `qdrant-client>=1.9.0` - Qdrant Python SDK
- `openai>=1.30.0` - OpenAI embeddings + chat completions for doc gen
- `PyGithub>=2.3.0` - GitHub API (list org repos)
- `gitpython>=3.1.43` - Git clone/pull operations
- `python-dotenv>=1.0.1` - Load .env
- `fastapi>=0.111.0` + `uvicorn[standard]>=0.30.0` - API server
- `pydantic>=2.7.0` + `pydantic-settings>=2.3.0` - Config + data models
- `lxml>=5.2.0` - XML parsing (handles malformed Odoo XML)
- `tiktoken>=0.7.0` - Token counting before embedding
- `httpx>=0.27.0` - Async HTTP for FastAPI

## Qdrant Collections Design

Three separate collections (enables type-specific search and filtering):

| Collection | Content | Key Metadata Filters |
|---|---|---|
| `odoo_code` | Python source chunks (classes, functions, module-level) | repo_name, module_name, chunk_type, file_path |
| `odoo_manifests` | Module manifests (one doc per module) | repo_name, module_name, module_category, module_depends |
| `odoo_views` | XML/HTML views, QWeb templates, data records | repo_name, module_name, xml_id, view_type, view_model |

All collections: 1536-dimension vectors, cosine distance, payload indexes on common filter fields.

## Chunking Strategy

- **Python files**: AST-based. Extract classes (whole class if <6000 tokens, else split into methods), standalone functions, module-level code. Context prefix: `"Module: X | File: Y | Class: Z"`.
- **XML/HTML files**: lxml-based. One chunk per `<record>`, `<template>`, `<menuitem>`. Extract xml_id, model, view_type metadata.
- **Manifests**: One chunk per module. Natural-language summary of all fields for embedding. All fields stored as metadata.
- **JS/CSS/other**: Line-based chunking, ~200 lines with 20-line overlap.

## Incremental Sync

- State stored in `sync_state.json`: maps `repo_name → last_synced_commit_sha`
- On sync: compare HEAD sha vs stored sha; skip unchanged repos
- For changed repos: `git diff --name-only` identifies affected files → only re-index modules containing changes
- Re-indexing a module: delete all old points for that module, then re-insert (simpler than diffing individual chunks)
- Deterministic point IDs via `uuid5(repo:module:file:chunk_name:start_line)` for idempotent upserts

## API Endpoints (consumed by OpenAI Custom GPT)

| Method | Path | Purpose |
|---|---|---|
| POST | `/search/code` | Search Python code chunks with filters (chunk_type, file_path) |
| POST | `/search/views` | Search XML views/templates with filters (view_type, view_model) |
| POST | `/search/manifests` | Search module metadata with filters (category, depends_on) |
| POST | `/search/all` | Search across all collections, merge by score |
| POST | `/docs/generate` | Generate markdown documentation for a module (uses GPT-4o-mini) |
| GET | `/health` | Health check + collection stats |

CORS configured for `chat.openai.com` and `chatgpt.com`. Auto-generated OpenAPI spec at `/openapi.json` imports directly into GPT Actions.

## GitHub Actions Workflow

- Cron: every 6 hours + manual `workflow_dispatch`
- Runs on `self-hosted` runner (localhost access to Qdrant)
- Steps: checkout → setup Python 3.11 → `pip install .` → `repo-sync` CLI
- Secrets: `ORG_GITHUB_TOKEN`, `OPENAI_API_KEY`, `GITHUB_ORG_NAME`
- Persistent sync state at `/opt/repo-sync/sync_state.json` on runner

## Implementation Order

### Phase 1: Foundation
1. Create `pyproject.toml` with all dependencies
2. Create `.env.example` with all config variables
3. Create `src/repo_sync/__init__.py`
4. Implement `src/repo_sync/config.py` (Pydantic Settings)
5. Implement `src/repo_sync/models.py` (ContentChunk, OdooModule, enums)

### Phase 2: Parsers
6. Create `src/repo_sync/sync/__init__.py` and `parsers/__init__.py`
7. Implement `manifest_parser.py` (simplest parser)
8. Implement `python_parser.py` (AST-based, most complex)
9. Implement `xml_parser.py` (lxml-based, Odoo-specific)
10. Implement `generic_parser.py` (line-based fallback)

### Phase 3: External Integrations
11. Implement `github_client.py` (PyGithub + GitPython)
12. Implement `odoo_discovery.py` (module detection)
13. Implement `embeddings.py` (OpenAI batch embedding)
14. Implement `qdrant_loader.py` (collection creation + upsert)
15. Implement `state.py` (incremental sync tracking)

### Phase 4: Pipeline Assembly
16. Implement `pipeline.py` (orchestrator)
17. Implement `cli.py` (entry point)
18. Create `docker-compose.yml` (Qdrant service)

### Phase 5: API Server
19. Implement `dependencies.py`, `schemas.py`
20. Implement `health.py` router
21. Implement `search.py` router (all 4 endpoints)
22. Implement `docs.py` router (doc generation)
23. Implement `app.py` (FastAPI factory + CORS)

### Phase 6: Deployment
24. Create `Dockerfile` for API server
25. Update `docker-compose.yml` (add API service)
26. Create `.github/workflows/sync.yml`
27. Update `README.md` with full documentation

## Verification

1. **Unit**: Run parsers against sample Odoo files, verify chunk output
2. **Integration**: Start Qdrant via `docker-compose up qdrant`, run `repo-sync` CLI against a test org/repo, verify points in Qdrant
3. **API**: Start API via `repo-sync-api`, test `/health`, `/search/code`, `/search/manifests` with curl
4. **OpenAPI**: Verify `/openapi.json` is valid and importable into GPT Actions
5. **GitHub Actions**: Trigger workflow manually via `workflow_dispatch`, check logs
