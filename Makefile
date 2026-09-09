.PHONY: venv install seed run worker test api

API=services/api

venv:
	cd $(API) && python3 -m venv .venv

install: venv
	cd $(API) && . .venv/bin/activate && pip install -r requirements.txt

seed:
	cd $(API) && . .venv/bin/activate && mkdir -p data && \
	  DATABASE_URL=$${DATABASE_URL:-sqlite:///./data/app.db} python -m app.seed

# Terminal 1: API only (upload leaves jobs queued)
run: seed
	cd $(API) && . .venv/bin/activate && \
	  DATABASE_URL=$${DATABASE_URL:-sqlite:///./data/app.db} \
	  ALLOW_DEV_LOGIN=true \
	  uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Terminal 2: pose extract worker (DB queue; no Redis)
# Windows: use Git Bash / WSL, or run the python -m line below in cmd/PowerShell after activating .venv
worker:
	cd $(API) && . .venv/bin/activate && \
	  DATABASE_URL=$${DATABASE_URL:-sqlite:///./data/app.db} \
	  python -m app.worker extract --loop

test:
	cd $(API) && . .venv/bin/activate && pytest -q

api: run
