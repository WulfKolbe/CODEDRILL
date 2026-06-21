PYTHON ?= python3
export PYTHONPATH := src

.PHONY: demo compile test languages clean check-env

demo:           ## run the bundled example
	$(PYTHON) -m codedrill demo

languages:      ## list registered language extractors
	$(PYTHON) -m codedrill languages

compile:        ## compile a tiddlers JSON: make compile IN=path.json OUT=drills/run
	$(PYTHON) -m codedrill compile $(IN) -o $(or $(OUT),drills/out)

test:           ## run the test suite
	$(PYTHON) tests/test_codedrill.py

check-env:      ## verify no .env is tracked by git (must print 0)
	@git ls-files | grep -c '^\.env$$' || true

clean:
	rm -rf drills/out drills/cdtest* build dist *.egg-info \
	       src/codedrill/__pycache__ src/codedrill/extractors/__pycache__ \
	       tests/__pycache__ .pytest_cache
