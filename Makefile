# Makefile — Raccourcis pour Happly AI

.PHONY: help start dev stop restart status migrate test lint logs backup

help: ## Affiche cette aide
	@echo "Commandes disponibles pour Happly AI :"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

start: ## Démarre tous les services (Docker + migrations)
	@./start.sh

dev: ## Démarre en mode développement (Postgres Docker + Backend & Frontend en local)
	@./start.sh dev

stop: ## Arrête tous les conteneurs (données conservées)
	@./infrastructure/scripts/stop.sh

restart: stop start ## Redémarre tous les services

status: ## Affiche l'état des conteneurs
	@docker compose ps

migrate: ## Applique les migrations de base de données Alembic
	@./infrastructure/scripts/migrate.sh

test: ## Exécute la suite de tests
	@./infrastructure/scripts/test.sh

lint: ## Vérifie le formatage et le typage (Ruff, mypy, ESLint)
	@./infrastructure/scripts/lint.sh

logs: ## Affiche les logs en direct (Ctrl+C pour quitter)
	@docker compose logs -f

backup: ## Sauvegarde la base de données
	@./infrastructure/scripts/backup.sh

