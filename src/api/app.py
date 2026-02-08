"""FastAPI application factory and uvicorn runner."""

from __future__ import annotations

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.dependencies import get_settings
from api.routers import docs, health, search


def create_app() -> FastAPI:
    load_dotenv()

    app = FastAPI(
        title="Repo Sync API",
        description="Search Odoo modules indexed in Qdrant vector database",
        version="0.1.0",
    )

    # CORS for OpenAI Custom GPT
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "https://chat.openai.com",
            "https://chatgpt.com",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router)
    app.include_router(search.router)
    app.include_router(docs.router)

    return app


app = create_app()


def main() -> None:
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "repo_sync.api.app:app",
        host=settings.fastapi_host,
        port=settings.fastapi_port,
        reload=False,
    )


if __name__ == "__main__":
    main()
