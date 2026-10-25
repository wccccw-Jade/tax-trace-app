PYTHON := .venv/bin/python
.PHONY: backup backup-drill install db db-stop db-status db-logs migrate import refresh audit test dev build
install:
	$(PYTHON) -m pip install -r requirements.txt
	cd frontend && npm install

db:
	docker compose up -d --wait
db-stop:
	docker compose stop db
db-status:
	docker compose ps db
db-logs:
	docker compose logs --tail=100 db
migrate:
	.venv/bin/alembic upgrade head
import:
	$(PYTHON) -m backend.cli import
refresh:
	$(PYTHON) -m backend.cli refresh
audit:
	$(PYTHON) -m backend.cli audit --output var/audit.json
	$(PYTHON) -m scripts.audit.report
test:
	$(PYTHON) -m pytest -q
dev:
	$(PYTHON) scripts/dev.py
build:
	cd frontend && npm run build

backup:
	$(PYTHON) -m scripts.backup create --directory var/backups/backup-$$(date +%Y%m%d-%H%M%S)
backup-drill:
	$(PYTHON) -m scripts.backup drill --directory var/backups/drill-$$(date +%Y%m%d-%H%M%S)
