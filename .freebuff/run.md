# Run guide — FinOps workspace

Workspace: `C:\Users\tejas\OneDrive\Desktop\FinOps` (main checkout; env files live here directly).

## Reproduce the uncommitted artifacts

This workspace is the primary checkout, so environment files are already in place:

- `.env` at the repo root (backend `DATABASE_URL` = `sqlite+aiosqlite:///./finops_local.db`, secret keys, etc.).
- `apps/web/.env.local` if present (frontend env: `BACKEND_INTERNAL_URL` / `NEXT_PUBLIC_API_BASE_URL`).
- `apps/web/node_modules` already installed (`npm install` if missing).
- Python deps installed in the active interpreter (`pip install -r requirements.txt` if missing).
- Local SQLite dev DB `finops_local.db` at the repo root — includes the identity tables and seeded roles (OPERATOR etc.). If missing, apply migrations and run the seed per `database/` tooling.

## Run the servers

### 1. Backend — FastAPI on :8000

```
uvicorn apps.api.main:app --host 0.0.0.0 --port 8000 --reload
```

Verify: `curl http://localhost:8000/health` → 200.

### 2. Frontend — Next.js dev server on :3000

IMPORTANT: the shell environment has `PORT=0` set, which makes `next dev` bind an ephemeral port. Always pass `-p 3000` explicitly:

```
cd apps/web
npm run dev -- -p 3000
```

Detached start (Windows, from `apps/web`):

```
powershell -NoProfile -Command '$p = Start-Process -FilePath "npm.cmd" -ArgumentList "run","dev","--","-p","3000" -RedirectStandardOutput "C:\Users\tejas\OneDrive\Desktop\FinOps\.freebuff\preview-ed01358e-a85c-4de0-880a-70d442a03647.log" -RedirectStandardError "C:\Users\tejas\OneDrive\Desktop\FinOps\.freebuff\preview-ed01358e-a85c-4de0-880a-70d442a03647.err.log" -WindowStyle Hidden -PassThru; $p.Id'
```

stdout and stderr MUST go to different files (PowerShell requirement). Verify the port and pid:

```
netstat -ano | grep ":3000" | grep LISTEN
```

Verify: `curl http://localhost:3000/login` → 200.

### Build / checks

- Frontend typecheck: `cd apps/web && npx tsc --noEmit`
- Frontend build: stop the dev server first (Windows/OneDrive `readlink` EINVAL when `.next` is in use), then `rm -rf apps/web/.next && cd apps/web && npm run build`
- Lint: `npm run lint` is currently broken repo-wide (Next 14 `next lint` + ESLint 9 + eslint-config-next 16 option mismatch) — do not attribute failures to workspace changes.
- Backend tests: `python -m pytest --tb=short -q`