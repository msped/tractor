SHELL := /bin/bash

VENV := env/bin/activate
DYLD_LIBS := /opt/homebrew/lib:/opt/homebrew/opt/libpq/lib

define backend
	source $(VENV) && export DYLD_FALLBACK_LIBRARY_PATH=$(DYLD_LIBS):$$DYLD_FALLBACK_LIBRARY_PATH && $(1)
endef

.PHONY: help \
	be-run be-worker be-migrate be-makemigrations \
	be-test be-test-cov be-lint be-format be-format-check \
	fe-dev fe-build fe-lint fe-cy-open fe-cy-run fe-cy-test \
	test lint

help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}' | sort

# ── Backend ──────────────────────────────────────────────────────────────────

be-run: ## Start Django dev server
	$(call backend,python manage.py runserver)

be-worker: ## Start django-q task queue worker
	$(call backend,python manage.py qcluster)

be-migrate: ## Apply database migrations
	$(call backend,python manage.py migrate)

be-makemigrations: ## Create new migrations
	$(call backend,python manage.py makemigrations)

be-test: ## Run backend tests
	$(call backend,python manage.py test)

be-test-cov: ## Run backend tests with coverage (90% threshold)
	$(call backend,coverage run manage.py test && coverage report --fail-under=90)

be-lint: ## Lint backend with ruff
	$(call backend,ruff check .)

be-format: ## Auto-format backend with ruff
	$(call backend,ruff format .)

be-format-check: ## Check backend formatting without writing
	$(call backend,ruff format --check .)

# ── Frontend ─────────────────────────────────────────────────────────────────

fe-dev: ## Start Next.js dev server
	cd frontend && npm run dev

fe-build: ## Build Next.js for production
	cd frontend && npm run build

fe-lint: ## Lint frontend with ESLint
	cd frontend && npm run lint

fe-cy-open: ## Open Cypress interactive mode
	cd frontend && npm run cy:open

fe-cy-run: ## Run Cypress tests headless
	cd frontend && npm run cy:run

fe-cy-test: ## Run Cypress tests with coverage report (80% threshold)
	cd frontend && npm run cy:test

# ── Combined ─────────────────────────────────────────────────────────────────

test: be-test fe-cy-run ## Run all tests (backend + frontend)

lint: be-lint fe-lint ## Lint everything (backend + frontend)
