# Send Me
Your Campus. Your Essentials. Delivered. Campus e-commerce and delivery for students in Ghana.

| Part | Where | State |
|---|---|---|
| API (FastAPI, SQLAlchemy, Alembic) | `backend/` | 67 automated tests pass |
| Web app (React + TypeScript + Tailwind PWA): student, shop dashboard, rider, administrator | `frontend/` | Built and exercised end to end in a browser |
| Browser end-to-end checks | `frontend/e2e/` | `student.cjs`, `platform.cjs` |

## See it running (2 minutes)
```bash
cd frontend && npm install && npm run build && cd ..
cd backend && python -m venv .venv && .venv/bin/pip install -r requirements.txt
export DATABASE_URL=sqlite:///./demo.db
.venv/bin/alembic upgrade head && .venv/bin/python -m app.seed_demo
.venv/bin/uvicorn app.main:app --port 8000
```
Open http://localhost:8000. Demo accounts (development only, password `demo12345`): student `0200000003`, shop manager `0200000002`, rider `0200000004`, administrator `0200000001`.

Without keys the app runs in **demo mode**: payments are simulated (clearly labelled), maps use OpenStreetMap, distances are straight-line estimates. See `ENVIRONMENT_VARIABLES.md` for what to set for production, `SETUP_GUIDE.md` for Windows steps, `PROJECT_STATUS.md` for current status.
