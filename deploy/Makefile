NAS_HOST ?= nas
NAS_PATH ?= /volume1/docker/sclca-financial-model
PROJECT_DIR := $(shell dirname $(realpath $(firstword $(MAKEFILE_LIST))))/..
DOCKER := /volume1/@appstore/ContainerManager/usr/bin/docker

.PHONY: sync build restart deploy logs

sync:
	rsync -avz --rsync-path=/usr/bin/rsync \
		--exclude='venv/' --exclude='__pycache__/' --exclude='*.xlsx' \
		--exclude='output/' --exclude='.git/' \
		"$(PROJECT_DIR)/" $(NAS_HOST):$(NAS_PATH)/

build:
	ssh $(NAS_HOST) "cd $(NAS_PATH)/deploy && $(DOCKER) compose build"

restart:
	ssh $(NAS_HOST) "cd $(NAS_PATH)/deploy && $(DOCKER) compose down && $(DOCKER) compose up -d"

deploy: sync build restart
	@echo "Deployed to NAS successfully"

logs:
	ssh $(NAS_HOST) "cd $(NAS_PATH)/deploy && $(DOCKER) compose logs -f --tail=50"
