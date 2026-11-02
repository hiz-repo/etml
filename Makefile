PYTHON ?= python3
ROOT := $(CURDIR)

.PHONY: test example references docs

test:
	PYTHONPATH=src $(PYTHON) -m unittest discover -s tests -v

example:
	$(PYTHON) scripts/check_story_examples.py

references:
	$(PYTHON) scripts/download_emotionml.py

docs:
	mkdir -p build/docs/emotionml build/docs/etml-spec
	cd docs/emotionml && latexmk -xelatex -interaction=nonstopmode -halt-on-error -outdir="$(ROOT)/build/docs/emotionml" main.tex
	cd docs/etml-spec && latexmk -xelatex -interaction=nonstopmode -halt-on-error -outdir="$(ROOT)/build/docs/etml-spec" main.tex
