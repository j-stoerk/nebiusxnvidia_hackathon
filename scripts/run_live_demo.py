"""Run a capped Token Factory demo; the API key stays in process memory."""
import argparse
import getpass
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--budget", type=float, default=.05, help="Cumulative local USD allowance, maximum 30")
    parser.add_argument("--requests", type=int, default=12)
    parser.add_argument("--port", type=int, default=8017)
    args = parser.parse_args()
    if not 0 < args.budget <= 30 or not 1 <= args.requests <= 100 or not 1024 <= args.port <= 65535:
        parser.error("Budget must be (0,30], requests 1–100, and port 1024–65535")
    from scripts.run_demo import build_frontend
    build_frontend()  # Build subprocesses never receive the key.
    key = getpass.getpass("Token Factory key (hidden, not saved): ").strip()
    if not key:
        raise SystemExit("No key supplied; no requests made")
    os.environ.update(NEBIUS_API_KEY=key, NEBIUS_MODEL="nvidia/Nemotron-3_5-Lightning",
        NEBIUS_BASE_URL="https://api.tokenfactory.nebius.com/v1", CLOUD_INFERENCE_ENABLED="true",
        CLOUD_INFERENCE_BUDGET_USD=str(args.budget), CLOUD_INFERENCE_MAX_REQUESTS=str(args.requests),
        CLOUD_INFERENCE_MAX_TOKENS="1024", NEMOTRON_BASE_URL="", NEMOTRON_MODEL="")
    del key
    import httpx
    with httpx.Client(timeout=30) as client:
        response = client.get("https://api.tokenfactory.nebius.com/v1/models", headers={"Authorization": "Bearer " + os.environ["NEBIUS_API_KEY"]})
    if response.status_code != 200:
        raise SystemExit(f"Model catalog HTTP {response.status_code}; no inference sent")
    if not any(m.get("id") == os.environ["NEBIUS_MODEL"] for m in response.json().get("data", [])):
        raise SystemExit("The verified-price model is unavailable; no inference sent")
    print(f"Live demo: http://127.0.0.1:{args.port}\nLocal allowance: ${args.budget:.2f}, at most {args.requests} requests. Prior reservations persist in .cache/cloud-inference-budget.json.\nPress Ctrl+C to stop and discard the in-memory key.", flush=True)
    import uvicorn
    uvicorn.run("backend.app.main:app", host="127.0.0.1", port=args.port)


if __name__ == "__main__":
    main()
