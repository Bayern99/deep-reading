PYTHON ?= .venv/bin/python
ISSUE ?= 2026-10-12
PORT ?= 8788

.PHONY: help test check smoke gate build reader studio hooks
help:
	@echo "make test | check | smoke | gate | build | reader | studio [ISSUE=YYYY-MM-DD] [PORT=8788]"
	@echo "make hooks  Install the tracked git hooks (data guard, pre-push check)"
	@echo "Bootstrap: python3 -m venv .venv && .venv/bin/python -m pip install -r requirements.txt"

test:
	PYTHONPATH=$(CURDIR)/render $(PYTHON) -m unittest discover -s tests -p 'test_*.py' -v
	PYTHONPATH=$(CURDIR)/render $(PYTHON) tests/test_p1.py

check: test smoke

hooks:
	ln -sf ../../scripts/hooks/commit-msg .git/hooks/commit-msg
	ln -sf ../../scripts/hooks/pre-push .git/hooks/pre-push
	chmod +x scripts/hooks/commit-msg scripts/hooks/pre-push
	@echo "Installed: .git/hooks/commit-msg (live data guard), .git/hooks/pre-push (make check)"

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
