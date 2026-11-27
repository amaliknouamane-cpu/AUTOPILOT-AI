"""Small starter benchmark for the integrated dashboard chatbot."""
import json
import statistics
import time

from .services.agents import run_agent
from .services.settings import CHATBOT_ROOT


def main():
    cases = json.loads((CHATBOT_ROOT / "evaluation_cases.json").read_text(encoding="utf-8"))
    results = []
    for case in cases:
        started = time.perf_counter()
        result = run_agent(case["message"])
        duration_ms = (time.perf_counter() - started) * 1000
        actual = result.get("route")
        results.append({
            "expected": case["expected_route"],
            "actual": actual,
            "correct": actual == case["expected_route"],
            "duration_ms": duration_ms,
        })
    latencies = [row["duration_ms"] for row in results]
    summary = {
        "cases": len(results),
        "route_accuracy": round(sum(row["correct"] for row in results) / max(1, len(results)), 3),
        "mean_latency_ms": round(statistics.mean(latencies), 2) if latencies else None,
        "p95_latency_ms": round(sorted(latencies)[max(0, int(len(latencies) * 0.95) - 1)], 2) if latencies else None,
        "details": results,
        "note": "Small starter fixture; extend before making quality claims.",
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

