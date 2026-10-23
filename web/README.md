# InvestIQ web UI

Vite + React front end (styling and layout adapted from the Codex-built UI) for
the real-company research workflow. It holds no secrets and never talks to
Moomoo directly: it calls the local Python API in `../api`, which calls the
existing, tested functions in `../frontend`.

## Run (two PowerShell terminals)

Prerequisite: Moomoo OpenD running and logged in on this computer.

Terminal 1 - API (project root, existing interpreter):

    cd "C:\Users\user\AI IGNITION FOLDER\team-powerpuffmen-snapshot-review"
    & "C:\Users\user\AI IGNITION FOLDER\team-powerpuffmen-agents\venv\Scripts\python.exe" -m pip install fastapi uvicorn
    & "C:\Users\user\AI IGNITION FOLDER\team-powerpuffmen-agents\venv\Scripts\python.exe" -m uvicorn api.server:app --host 127.0.0.1 --port 8000

Terminal 2 - UI:

    cd "C:\Users\user\AI IGNITION FOLDER\team-powerpuffmen-snapshot-review\web"
    npm install
    npm run dev

Open http://127.0.0.1:5173

## Checks

    python -m pytest tests          # Python, offline (fake Moomoo SDK)
    cd web && npm test              # UI behaviour (simulated DOM)
    cd web && npm run build         # type check + production build

## Behaviour to rely on

- An error is shown as an error. No sample data is substituted.
- Optional statement profit that fails validation is recorded as a recovery
  warning; profit stays unavailable and the screen continues on snapshot volume.
- Market cap and previous close stay withheld (USD mapping unverified), so the
  screen is always labelled incomplete.
