import html
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from app.api.ws_handler import build_websocket_endpoint
from app.application.live_session_service import LiveSessionService
from app.touch_base.agent import build_root_agent
from app.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI()
    app.mount("/static", StaticFiles(directory=settings.static_dir), name="static")

    index_path = Path(settings.static_dir) / "index.html"
    index_template = index_path.read_text(encoding="utf-8")

    @app.get("/")
    async def root():
        injected = index_template.replace(
            "__PUBLIC_APP_URL__",
            html.escape(settings.public_app_url, quote=True),
        )
        return HTMLResponse(content=injected)

    live_session_service = LiveSessionService(
        app_name=settings.app_name,
        root_agent=build_root_agent(),
        voice_name=settings.voice_name,
    )
    app.websocket("/ws/{session_id}")(build_websocket_endpoint(live_session_service))
    return app


app = create_app()
