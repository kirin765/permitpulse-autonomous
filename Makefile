SHELL := /bin/bash

.PHONY: bootstrap up down test lint format ingest autonomy

bootstrap:
	python3 -m pip install -r backend/requirements.txt
	npm install

up:
	docker compose up --build

down:
	docker compose down -v

test:
	cd backend && python3 manage.py test

lint:
	cd backend && python3 -m compileall .
	npm run lint

ingest:
	cd backend && python3 manage.py run_data_loop

autonomy:
	cd backend && python3 manage.py run_autonomy_cycle
