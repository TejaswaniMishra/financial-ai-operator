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

#### If the backend serves stale routes (404 on /api/v1/exceptions, /periods, /reports)

`uvicorn --reload` can silently serve outdated code on this OneDrive-backed
checkout in two ways:

1. **Orphaned reloader worker**: if the original `uvicorn --reload` parent was
   killed, its `multiprocessing.spawn` child can survive and keep holding the
   :8000 socket, accepting all new connections with the OLD code. `netstat`
   may show a ghost LISTENING pid that `tasklist` says does not exist.
   Diagnosis: `curl http://localhost:8000/openapi.json` and check whether
   `/api/v1/exceptions`, `/api/v1/periods`, `/api/v1/reports/*` are present;
   if missing while `apps/api/main.py` registers them, the server is stale.
   Fix: enumerate `python.exe` processes (PowerShell `Get-CimInstance
   Win32_Process -Filter "Name='python.exe'"`), `taskkill //F //PID <pid> //T`
   every uvicorn tree, confirm `netstat` shows no :8000 listener, then start
   fresh with the command above.
2. **Stale `__pycache__`**: OneDrive timestamp collisions can make Python
   trust an old `.pyc`. If a fresh `python -c "from apps.api.main import app"`
   still misses routers, purge bytecode caches:
   `find . -path ./node_modules -prune -o -name "__pycache__" -type d -exec rm -rf {} +`
   and restart.

After either fix, re-verify `/openapi.json` lists all 57 routes.

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

### Second preview instance (e.g. another thread / port)

Two `next dev` servers CANNOT share this worktree's `apps/web/.next` — the
second one dies with OneDrive `readlink EINVAL` on `.next/static/chunks`
while the first is running. To serve a second instance of the same code:

1. Copy the web app to a scratch dir with its own `.next` and node_modules:
   ```
   rm -rf "$(cygpath -w /tmp/finops-preview-web 2>/dev/null || echo /tmp/finops-preview-web)"
   MSYS_NO_PATHCONV=1 robocopy "$(cygpath -w apps/web)" "$(cygpath -w /tmp/finops-preview-web)" /E /XD .next
   ```
   (robocopy needs Windows paths and `/E` must not be POSIX-converted.)
2. Start it on a free port from that scratch dir (log paths must differ):
   ```
   powershell -NoProfile -Command "(Start-Process -FilePath 'npm.cmd' -ArgumentList 'run','dev','--','-p','3002' -RedirectStandardOutput '<log>' -RedirectStandardError '<log>.err' -WorkingDirectory 'C:\Users\tejas\AppData\Local\Temp\finops-preview-web' -WindowStyle Hidden -PassThru).Id"
   ```
   The frontend defaults to the backend at `http://localhost:8000`.

### Build / checks

- Frontend typecheck: `cd apps/web && npx tsc --noEmit`
- Frontend build: stop the dev server first (Windows/OneDrive `readlink` EINVAL when `.next` is in use), then `rm -rf apps/web/.next && cd apps/web && npm run build`
- Lint: `npm run lint` is currently broken repo-wide (Next 14 `next lint` + ESLint 9 + eslint-config-next 16 option mismatch) — do not attribute failures to workspace changes.
- Backend tests: `python -m pytest --tb=short -q`