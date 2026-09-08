.PHONY: venv install seed run test api

API=services/api

venv:
	cd $(API) && python3 -m venv .venv

install: venv
	cd $(API) && . .venv/bin/activate && pip install -r requirements.txt

seed:
	cd $(API) && . .venv/bin/activate && mkdir -p data && \
	  DATABASE_URL=$${DATABASE_URL:-sqlite:///./data/app.db} python -m app.seed

run: seed
	cd $(API) && . .venv/bin/activate && \
	  DATABASE_URL=$${DATABASE_URL:-sqlite:///./data/app.db} \
	  ALLOW_DEV_LOGIN=true \
	  uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

test:
	cd $(API) && . .venv/bin/activate && pytest -q

api: run
