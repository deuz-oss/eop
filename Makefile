API_DIR := services/api

.PHONY: migrate downgrade revision history current

migrate:
	cd $(API_DIR) && uv run alembic upgrade head

downgrade:
	cd $(API_DIR) && uv run alembic downgrade -1

revision:
	cd $(API_DIR) && uv run alembic revision --autogenerate -m "$(MESSAGE)"

history:
	cd $(API_DIR) && uv run alembic history

current:
	cd $(API_DIR) && uv run alembic current
