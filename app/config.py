"""Application settings, read from environment variables (with safe defaults)."""
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

# Loads a local .env file if present; real environment variables always win.
load_dotenv(BASE_DIR / ".env")


@dataclass(frozen=True)
class Settings:
    database_url: str
    certificates_dir: Path


def _resolve_dir(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else BASE_DIR / path


def load_settings() -> Settings:
    return Settings(
        database_url=os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'certificates.db'}"),
        certificates_dir=_resolve_dir(os.getenv("CERTIFICATES_DIR", "generated_certificates")),
    )


settings = load_settings()
