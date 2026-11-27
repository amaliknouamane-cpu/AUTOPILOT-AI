

import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv

# Find .env in the main AutoPilotAI folder
PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = PROJECT_ROOT / ".env"

load_dotenv(ENV_FILE)

DATABASE_URL = os.getenv("DATABASE_URL")


def get_connection():
    if not DATABASE_URL:
        raise RuntimeError(
            f"DATABASE_URL is missing. Check this file: {ENV_FILE}"
        )

    return psycopg.connect(DATABASE_URL)

