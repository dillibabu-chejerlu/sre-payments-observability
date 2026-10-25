.PHONY: install test lint up down logs load chaos-errors chaos-latency chaos-off k8s-apply

install:        ## install dev dependencies
	pip install -r requirements-dev.txt
test:           ## run unit tests
	pytest -q
lint:
	ruff check .
up:             ## start app + Prometheus + Alertmanager + Grafana
	docker compose up -d --build
down:
	docker compose down -v
logs:
	docker compose logs -f payments-api
load:           ## generate traffic for 5 minutes
	python scripts/load_test.py --rps 20 --duration 300
chaos-errors:   ## 30% of requests fail -> fast-burn alert
	./scripts/chaos.sh errors
chaos-latency:  ## +800ms latency -> p99 alert
	./scripts/chaos.sh latency
chaos-off:
	./scripts/chaos.sh off
k8s-apply:
	kubectl apply -f k8s/namespace.yaml && kubectl apply -f k8s/
