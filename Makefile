# vim:ft=make

COMNETSEMU = comnetsemu/*.py
CE_BIN = bin/ce
UNITTESTS = comnetsemu/test/unit/*.py
TESTS = $(UNITTESTS) comnetsemu/test/*.py
EXAMPLES = examples/*.py
PYSRC = $(COMNETSEMU) $(EXAMPLES) $(CE_BIN) $(TESTS)
PYTHON ?= python3
PYTYPE = pytype
CHECKERRIGNORE=E501,W605
PREFIX ?= /usr
DOCDIRS = doc/html doc/latex

CFLAGS += -Wall -Wextra

all: errcheck

clean:
	rm -rf build dist *.egg-info *.pyc $(DOCDIRS)

codecheck: $(PYSRC)
	@echo "*** Running checks for code quality"
	$(PYTHON) -m flake8 --extend-ignore=E501 --max-complexity 10 $(PYSRC)
	$(PYTHON) -m pylint --rcfile=.pylint $(PYSRC)

errcheck: $(PYSRC)
	@echo "*** Running checks for errors only"
	$(PYTHON) -m flake8 --extend-ignore=$(CHECKERRIGNORE) $(PYSRC)
	$(PYTHON) -m pylint -E --rcfile=.pylint $(PYSRC)

typecheck: $(PYSRC)
	@echo "*** Running type checks with $(PYTYPE)..."
	$(PYTYPE) $(COMNETSEMU)

test-examples: $(COMNETSEMU) $(EXAMPLES)
	cd ./examples && bash ./run.sh

test-examples-all: $(COMNETSEMU) $(EXAMPLES)
	cd ./examples && bash ./run.sh -a

test: $(COMNETSEMU) $(UNITTESTS)
	@echo "Running all unit tests of ComNetsEmu python package."
	$(PYTHON) ./comnetsemu/test/unit/runner.py -v

coverage: $(COMNETSEMU) $(UNITTESTS)
	@echo "Running coverage tests of ComNetsEmu core functions."
	$(PYTHON) -m coverage run --source ./comnetsemu ./comnetsemu/test/unit/runner.py -v
	$(PYTHON) -m coverage report -m

installercheck: ./util/install.sh
	@ echo "*** Check installer"
	bash ./check_installer.sh

format: $(PYSRC)
	@echo "Format Python sources with black"
	black $(PYSRC)


install:
	$(PYTHON) setup.py install

develop: $(MNEXEC) $(MANPAGES)
	$(PYTHON) setup.py develop

.PHONY: doc

doc: $(PYSRC)
	@echo "Build documentation in HTML format"
	cd ./doc/ && make html

build-test-containers:
	@echo "Build all test containers"
	cd ./test_containers/ && ./build.sh -a

## Cleanup utilities

rm-all-containers:
	@echo "Remove all docker containers"
	docker container rm $$(docker ps -aq) -f

rm-dangling-images:
	@echo "Remove all dangling docker images"
	docker rmi $$(docker images -f "dangling=true" -q)

pp-empty-dirs:
	@echo "Print empty directories"
	@find -maxdepth 3 -type d -empty
