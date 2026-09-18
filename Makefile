IMAGE   := pwighton/fs-centilebrain
VERSION := $(shell sed -n 's/^version *= *"\([^"]*\)".*/\1/p' pyproject.toml)
TAG     := $(IMAGE):$(VERSION)

.PHONY: build test push version

build:
	docker build -t $(TAG) -t $(IMAGE):latest .

test: build
	docker run --rm --entrypoint pytest $(TAG) -q

push: build
	docker push $(TAG)
	docker push $(IMAGE):latest

version:
	@echo $(VERSION)
