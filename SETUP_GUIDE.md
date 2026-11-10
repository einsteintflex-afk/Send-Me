# Setup guide (Windows + VS Code)

Install: Python 3.12+ (tick "Add to PATH"), Git, VS Code, Docker Desktop (optional, for PostgreSQL).

```powershell
git clone https://github.com/einsteintflex-afk/Send-Me.git
cd Send-Me\backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env      # then edit .env; for quick local use set DATABASE_URL=sqlite:///./sendme.db
alembic upgrade head
python -m app.seed
uvicorn app.main:app --reload
```
API docs open at http://localhost:8000/docs.

## Create the first admin
Set `SEED_ADMIN_EMAIL`, `SEED_ADMIN_PASSWORD`, `SEED_ADMIN_PHONE` in `.env`, then run `python -m app.seed` again.

## Load products
Fill a CSV (header: `name,category,price,variant,availability,stock_qty,description`; template in `backend/data/catalog_template.csv`), then:
```powershell
python -m app.scripts.import_catalog data\catalog.csv --dry-run
python -m app.scripts.import_catalog data\catalog.csv
```
Blank price stays blank. Category must be a slug such as `drinks`, `snacks`, `noodles`.

## Run tests
```powershell
pytest -q
```

## PostgreSQL with Docker
```powershell
cd ..
docker compose up --build
```

## Production notes
- Run behind HTTPS (Caddy, Nginx or a platform like Render/Railway/Fly). Set `ENV=production` and a real `JWT_SECRET`.
- Run `alembic upgrade head` on each deploy (the Dockerfile does).
- Back up PostgreSQL daily (`pg_dump`) and back up the uploads volume. Test a restore before launch.
- Add the Paystack webhook URL (see ENVIRONMENT_VARIABLES.md).
