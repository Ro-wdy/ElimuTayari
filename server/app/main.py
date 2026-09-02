from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import get_settings
from app.db import create_db_engine, create_session_factory
from app.routes import health, sms, ussd


def create_app(database_url: str | None = None) -> FastAPI:
    """Build the application.

    database_url overrides the configured DATABASE_URL, which is how tests point
    the app at a throwaway database.
    """
    settings = get_settings()
    if database_url is not None:
        settings.database_url = database_url

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        engine = create_db_engine(settings.database_url)
        app.state.engine = engine
        app.state.session_factory = create_session_factory(engine)
        try:
            yield
        finally:
            engine.dispose()

    app = FastAPI(title="ElimuTayari", version="0.1.0", lifespan=lifespan)
    app.state.settings = settings
    app.include_router(health.router)
    app.include_router(ussd.router)
    app.include_router(sms.router)
    return app


app = create_app()
