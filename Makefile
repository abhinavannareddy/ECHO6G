.PHONY: install test benchmark web build deploy stop
install:
	python -m pip install -e ".[dev]"
test:
	python -m pytest -q
benchmark:
	python -m echo6g.cli --output results --seed 2026 --scenarios 160
web:
	echo6g-web
build:
	python -m pip wheel --no-deps --no-build-isolation . --wheel-dir dist
deploy:
	docker compose up --build -d
stop:
	docker compose down
