from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    project_root: Path
    static_dir: Path
    docs_dir: Path
    chroma_db_dir: Path
    ingestion_cache_file: Path
    team_directory_file: Path
    calendar_token_path: Path
    credentials_path: Path
    app_name: str
    voice_name: str
    timezone_fallback: str
    # Shown in the UI for demos; use "local" to display the real browser origin instead.
    public_app_url: str


def get_settings() -> Settings:
    load_dotenv()

    project_root = Path(__file__).resolve().parents[1]
    token_default = Path(os.path.expanduser("~/.credentials/calendar_token.json"))
    secrets_dir = project_root / "secrets"

    return Settings(
        project_root=project_root,
        static_dir=Path(__file__).resolve().parent / "static",
        # Ingestion corpus: company-owned documents (PDFs only).
        docs_dir=project_root / "company_docs",
        chroma_db_dir=project_root / "chroma_db",
        ingestion_cache_file=project_root / "ingestion_cache.json",
        team_directory_file=project_root / "team_directory.json",
        calendar_token_path=Path(os.getenv("CALENDAR_TOKEN_PATH", str(token_default))),
        credentials_path=Path(
            os.getenv(
                "GOOGLE_OAUTH_CREDENTIALS_PATH",
                str(secrets_dir / "credentials.json"),
            )
        ),
        app_name=os.getenv("APP_NAME", "ADK Streaming example"),
        voice_name=os.getenv("VOICE_NAME", "Puck"),
        timezone_fallback=os.getenv("TIMEZONE_FALLBACK", "Africa/Cairo"),
        public_app_url=os.getenv(
            "PUBLIC_APP_URL",
            "https://touch-base.internal",
        ).strip()
        or "https://touch-base.internal",
    )
