from datetime import datetime, timezone
import hashlib
import json
import time
from uuid import uuid4

from .settings import OBSERVABILITY_PATH


class RunRecorder:
    def __init__(self, user_text: str):
        self.run_id = str(uuid4())
        self.started = time.perf_counter()
        self.query_fingerprint = hashlib.sha256(user_text.encode("utf-8")).hexdigest()[:16]

    def finish(self, *, route: str, success: bool, sources: int = 0, error: str | None = None):
        record = {
            "run_id": self.run_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "query_fingerprint": self.query_fingerprint,
            "route": route,
            "success": success,
            "duration_ms": round((time.perf_counter() - self.started) * 1000, 2),
            "source_count": sources,
            "error_type": error,
        }
        OBSERVABILITY_PATH.parent.mkdir(parents=True, exist_ok=True)
        with OBSERVABILITY_PATH.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, ensure_ascii=False) + "\n")
        return record

