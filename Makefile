.PHONY: help run submodules
REPO_NAME ?= aws-ocp
VENV_NAME?=venv
VENV_ACTIVATE=. $(VENV_NAME)/bin/activate
PYTHON=${VENV_NAME}/bin/python3
PYTHON3 := $(shell python3 -V 2>&1)
FUNCTIONS=GenerateIgnitionFiles DeployCF
DOCKER_REGISTRY ?= example.com
IMAGE ?= lambda_builder
TAG ?= test

help:
	@echo   "make test  : executes taskcat"

.ONESHELL:
test: lint build_lambda
	taskcat test run -n

lint:
	time taskcat lint

# Builds the lambda zip inside of the docker container
build_docker:
	docker build -t $(DOCKER_REGISTRY)/$(IMAGE):$(TAG) .

# Copies the lambda zip from the docker container to functions/packages
build_lambda:	build_docker
	docker run -it --rm \
	-v "$(shell pwd)/functions:/dest_functions" \
	$(DOCKER_REGISTRY)/$(IMAGE):$(TAG) \
	-c "/bin/cp -R packages /dest_functions/"

verify:
ifdef PYTHON3
	@echo "python3 Found, continuing."
else
	@echo "please install python3"
	exit 1
endif

venv:
	@make verify
	python3 -m venv $(VENV_NAME);

# Make sure to export all of the parameters found in LambdaStack resource in
# templates/aws-ocp-master.template.yaml as env variables
run_lambda_create_cf: venv
	${VENV_ACTIVATE} && \
	cd functions/source/OpenShift4Installation/ && \
	python-lambda-local -f lambda_handler lambda_function.py ../../tests/deploy_cf_env_variables.json -t 300
