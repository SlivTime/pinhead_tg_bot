ifneq (,$(wildcard .env))
    $(info Found .env file.)
    include .env
	export
endif

SERVICE_NAME=pinhead
PYTHON_VERSION=3.11.4

.PHONY: deps build

deps:
	pip install --upgrade pip && \
	pip install -r requirements-dev.txt
	pre-commit install --install-hooks

run:
	python main.py

poll:
	python main.py --polling

lint:
	pre-commit run --all-files

build:
	docker build --tag ${SERVICE_NAME} --no-cache .

pyenv:
	echo ${SERVICE_NAME} > .python-version && pyenv install -s 3.11.4 && pyenv virtualenv -f 3.11.4 ${SERVICE_NAME}

pyenv-delete:
	pyenv virtualenv-delete -f ${SERVICE_NAME}
