# Deployment guide

## Local development

1. Create a virtualenv and install backend deps:

```powershell
python -m venv .venv
.\.venv\Scripts\pip install -r backend\requirements.txt
```

2. Optional: copy `.env.example` to `.env` and set Nebius credentials for the AI agent.

3. Start the API:

```powershell
.\.venv\Scripts\uvicorn.exe backend.app.main:app --reload --port 8000
```

4. Start the frontend (separate terminal):

```powershell
cd frontend
npm install
npm run dev
```

Open http://127.0.0.1:5173 (Vite proxies `/api` to port 8000).

## Production-style single process

```powershell
cd frontend
npm install
npm run build
cd ..
.\.venv\Scripts\uvicorn.exe backend.app.main:app --host 0.0.0.0 --port 8000
```

FastAPI serves `frontend/dist` when present.

## Frontend container

```powershell
cd frontend
docker build -t chargewise-frontend .
docker run -p 8080:80 chargewise-frontend
```

Point the UI at your API or place a reverse proxy in front of both services.

## Security notes

- Never commit real API keys. Use `.env` (gitignored).
- This MVP stores schedules in memory only; restarting the process clears state.
