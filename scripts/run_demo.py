"""Build if needed, start ChargeWise, and open its guided demo. No model downloads."""

import argparse
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser

ROOT = Path(__file__).resolve().parents[1]


def build_frontend():
    frontend = ROOT / "frontend"
    index = frontend / "dist" / "index.html"
    sources = [*frontend.joinpath("src").rglob("*"), *[frontend / name for name in ("package.json", "package-lock.json", "vite.config.js", "tsconfig.json", "index.html")]]
    if index.exists() and all(p.stat().st_mtime <= index.stat().st_mtime for p in sources if p.is_file()):
        return
    npm = shutil.which("npm.cmd" if os.name == "nt" else "npm")
    if not npm:
        raise SystemExit("Node.js/npm is required for the frontend build. Install Node.js 22.12+ or 24+ and retry.")
    installed_lock = frontend / "node_modules" / ".package-lock.json"
    if not installed_lock.is_file() or installed_lock.stat().st_mtime < (frontend / "package-lock.json").stat().st_mtime:
        subprocess.run([npm, "ci", "--no-audit", "--no-fund"], cwd=frontend, check=True)
    subprocess.run([npm, "run", "build"], cwd=frontend, check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--host", choices=["127.0.0.1", "0.0.0.0"], default="127.0.0.1")
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error("Use a port between 1024 and 65535")
    os.chdir(ROOT)
    sys.path.insert(0, str(ROOT))
    build_frontend()
    url = f"http://127.0.0.1:{args.port}"
    with socket.socket() as probe:
        occupied = probe.connect_ex(("127.0.0.1", args.port)) == 0
    if occupied:
        try:
            with urllib.request.urlopen(url + "/api/health", timeout=2) as response:
                existing = json.load(response)
            if existing.get("application") != "chargewise":
                raise ValueError("Different application")
        except (OSError, ValueError):
            raise SystemExit(f"Port {args.port} is in use by another service. Choose --port with a free port.")
        print(f"ChargeWise is already running. Open {url}/?demo=1", flush=True)
        if not args.no_browser:
            webbrowser.open(url + "/?demo=1")
        return

    def open_ready():
        for _ in range(40):
            try:
                with urllib.request.urlopen(url + "/api/health", timeout=1) as response:
                    if response.status == 200:
                        webbrowser.open(url + "/?demo=1")
                        return
            except OSError:
                time.sleep(.25)

    print(f"Guided demo: {url}/?demo=1\nPress Ctrl+C to stop. AI is optional and clearly labeled if disconnected.", flush=True)
    if not args.no_browser:
        threading.Thread(target=open_ready, daemon=True).start()
    import uvicorn
    uvicorn.run("backend.app.main:app", host=args.host, port=args.port)


if __name__ == "__main__":
    main()
