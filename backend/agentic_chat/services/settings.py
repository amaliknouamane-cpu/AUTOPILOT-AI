from pathlib import Path
import os

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[3]
CHATBOT_ROOT = PROJECT_ROOT / "backend" / "agentic_chat"
DATA_DIR = CHATBOT_ROOT / "data"
KNOWLEDGE_DIR = CHATBOT_ROOT / "knowledge"
DATA_DIR.mkdir(exist_ok=True)

load_dotenv(PROJECT_ROOT / ".env")

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434").rstrip("/")
CHAT_MODEL = os.getenv("OLLAMA_CHAT_MODEL", os.getenv("OLLAMA_MODEL", "llama3.2"))
EMBED_MODEL = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")
INDEX_PATH = DATA_DIR / "knowledge.sqlite3"
OBSERVABILITY_PATH = DATA_DIR / "observability.jsonl"

