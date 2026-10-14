PYTHON ?= .venv/bin/python
ISSUE ?= 2026-10-12
PORT ?= 8788

.PHONY: help test smoke build reader studio gate
help:
	@echo "make test | smoke | gate | build | reader | studio [ISSUE=YYYY-MM-DD] [PORT=8788]"
	@echo "Bootstrap: python3 -m venv .venv && .venv/bin/python -m pip install -r requirements.txt"

test:
	PYTHONPATH=$(CURDIR)/render $(PYTHON) -m unittest discover -s tests -p 'test_*.py' -v
	PYTHONPATH=$(CURDIR)/render $(PYTHON) tests/test_p1.py

smoke:
	$(PYTHON) scripts/smoke.py --issue $(ISSUE)

gate:
	$(PYTHON) render/integrity_gate.py $(ISSUE)/final.json

build:
	$(PYTHON) render/build.py --issue $(ISSUE)

reader:
	$(PYTHON) render/editorial_studio.py --issue $(ISSUE)

studio:
	$(PYTHON) render/editorial_studio.py --issue $(ISSUE) --serve --port $(PORT)
