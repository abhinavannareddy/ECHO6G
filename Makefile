.PHONY: install test benchmark web build deploy stop
install:
	python -m pip install -e .
test:
	docker build --target test -t echo6g-tests .
benchmark:
	python -m echo6g.cli --output results --seed 2026 --scenarios 160
web:
	echo6g-web
build:
	docker compose build
deploy:
	docker compose up --build -d
stop:
	docker compose down
