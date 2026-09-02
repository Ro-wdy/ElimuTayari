from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import get_settings
from app.db import create_db_engine, create_session_factory
from app.llm_client import AnthropicLlmClient, LlmClient
from app.routes import health, sms, ussd
from app.sms_client import AfricasTalkingSmsClient, SmsClient


def create_app(
    database_url: str | None = None,
    sms_client: SmsClient | None = None,
    llm_client: LlmClient | None = None,
) -> FastAPI:
    """Build the application.

    database_url overrides the configured DATABASE_URL, which is how tests point
    the app at a throwaway database. sms_client and llm_client override the real
    Africa's Talking and Anthropic clients, which is how tests capture outbound
    SMS and stub Claude responses.
    """
    settings = get_settings()
    if database_url is not None:
        settings.database_url = database_url
    if sms_client is None:
        sms_client = AfricasTalkingSmsClient(
            settings.africastalking_username,
            settings.africastalking_api_key,
            settings.africastalking_sender_id,
        )
    if llm_client is None:
        llm_client = AnthropicLlmClient(
            settings.anthropic_api_key, settings.anthropic_workspace_id
        )

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
    app.state.sms_client = sms_client
    app.state.llm_client = llm_client
    app.include_router(health.router)
    app.include_router(ussd.router)
    app.include_router(sms.router)
    return app


app = create_app()
