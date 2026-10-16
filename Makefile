PYTHON ?= .venv/bin/python
TRACER_PYTHON ?= /opt/homebrew/bin/python3
TRACER_OUT ?= /tmp/wsj-2026-10-14.html
TRACER_GATE ?= /tmp/gate-report.json
TRACER_CERT ?= /tmp/oracle-certification.json

.PHONY: help test check smoke hooks tracer tracer-certify
help:
	@echo "make test | check | smoke"
	@echo "make tracer | tracer-certify  2026-10-14 Issue Artifact (+ LQA / 7-Oracle)"
	@echo "make hooks  Install the tracked git hooks (data guard, pre-push check)"
	@echo "Bootstrap: python3 -m venv .venv && .venv/bin/python -m pip install -r requirements.txt"

test:
	PYTHONPATH=$(CURDIR)/render $(PYTHON) -m unittest discover -s tests -p 'test_*.py' -v

check: test smoke

hooks:
	ln -sf ../../scripts/hooks/commit-msg .git/hooks/commit-msg
	ln -sf ../../scripts/hooks/pre-push .git/hooks/pre-push
	chmod +x scripts/hooks/commit-msg scripts/hooks/pre-push
	@echo "Installed: .git/hooks/commit-msg (live data guard), .git/hooks/pre-push (make check)"

smoke:
	$(PYTHON) scripts/smoke.py --fast

tracer:
	$(TRACER_PYTHON) render/tracer_pipeline.py --mode full --output $(TRACER_OUT) --gate-report $(TRACER_GATE)

tracer-certify:
	$(TRACER_PYTHON) render/tracer_pipeline.py --mode full --output $(TRACER_OUT) --gate-report $(TRACER_GATE) --certify $(TRACER_CERT)
