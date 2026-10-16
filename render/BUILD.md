# Daily Issue Artifact compilation

Run from the repository root after [README setup](../README.md#install). Read [FOUNDATION](../FOUNDATION.md) and [DESIGN](../DESIGN.md) before building or restyling; read [ARCHITECTURE](../ARCHITECTURE.md) before changing contracts.

The product commands are `make tracer` / `make tracer-certify` and `make check` ([ADR 0002](../docs/adr/0002-issue-artifact-only-product.md)). Frozen Studio-era runtime: git branch `archive/studio-phase1-7`.

## Offline verification

```bash
make test
make smoke
make tracer-certify
```

`make test` discovers `tests/test_*.py`: `tests/test_vertical_tracer.py`, `tests/test_full_issue_gate_cli.py`, `tests/test_seven_oracles.py`. `make smoke` runs `scripts/smoke.py --fast` (no `fitz`/`PIL`; not a publishable Issue Artifact). `make check` is test + smoke.

84 of the 102 tests read the pinned pilot dataset and print PDF. When those pins are absent the suites fail with `RuntimeError: pinned pilot inputs are missing ...` rather than skipping quietly, because a run in which every data-backed test skipped still exits 0 and would report OK without checking the product. Set `WSJ_ALLOW_MISSING_PILOT=1` to skip them instead, which leaves the ~18 fixture-free tests running; that is the mode for a machine with no pinned inputs. `fitz`/`PIL` absent is a separate, legitimate skip. Restoring the pins: [data policy](../docs/data-policy.md) (Backup and restore).

## Compile the Issue Artifact (2026-10-14 pilot)

```bash
make tracer          # full-issue artifact + LQA Funnel report
make tracer-certify  # ... + seven Certification Oracles
```

Equivalent:

```bash
/opt/homebrew/bin/python3 render/tracer_pipeline.py --mode full \
    --output /tmp/wsj-2026-10-14.html --gate-report /tmp/gate-report.json

/opt/homebrew/bin/python3 render/tracer_pipeline.py --mode full \
    --output /tmp/wsj-2026-10-14.html --gate-report /tmp/gate-report.json \
    --certify /tmp/oracle-certification.json
```

Requires the pinned pilot dataset and print PDF in `render/tracer/compose.py` (`PILOT_ROOT`, `PDF_PATH`, `PDF_SHA256`). Python 3.11+, `lxml` always; `fitz` (PyMuPDF) + `PIL` for non-`--fast` runs. `TRACER_PYTHON` / `TRACER_OUT` / `TRACER_GATE` / `TRACER_CERT` override make defaults.

`--mode full` compiles the 86-item 2026-10-14 issue into one Issue Artifact (~71 units: 8 Tier 1, 54 Tier 2, 9 Tier 3; target 5–8 MB, budget [4.5 MB, 10 MB]). `--mode tracer` keeps the five-unit slice; `--units id,...` filters; `--fast` skips PDF raster work.

The LQA Funnel (`render/tracer/gate.py`) runs a two-stage radar over bilingual units. Stage-2 findings are dispositions, not rewrites. `gate-report.json` sits next to the output and is never embedded in the Reader HTML.

The seven Certification Oracles (`render/tracer/oracles.py`) inspect the generated HTML:

1. SHA256 narrative round-trip for all 86 raw items.
2. Paragraph-scoped numeric grounding of every authored element, including Forensic Dossier containers.
3. `Retina*` chart vector coverage for all 21 printed charts, paired Chart Companions.
4. Figure print-order monotonicity and print-ad exclusion.
5. 6/6 historical fault-injection recall.
6. Print hierarchy (86→71 units, 7 canonical sections, 16/16 deep links, zero Tier 2 lede restatement).
7. Payload budget, zero forbidden pipeline strings, Headless Chrome geometry (1440×900 and 390×844 in 中文/EN/双语).

`--certify` exits non-zero on any oracle failure. The certification JSON is a workspace report, never Reader chrome.

## Agent Skill

Cloud / bot VM entry: [skills/wsj-deep-read/SKILL.md](../skills/wsj-deep-read/SKILL.md). Same CLI as `make tracer-certify`.

## Recovery

There is no persistent queue on this path. If a run fails, keep the partial HTML and workspace JSON for diagnosis, then rerun. Do not publish `--fast` output.

The print PDF and `PILOT_ROOT` live outside Git. Losing either breaks compilation until the pins are restored. Stop treating `2026-10-12/editorial-artifacts/_queue.json` as a recovery surface for daily publishing.

## Next real issue

A second date needs its own inventory, reviewed translations, Primary Vector Signals and oracle fixtures. The repository does not yet provide that upstream runner. Do not revive historical `assemble.py` over an accepted source, and do not publish another date through Studio.

See remaining risks in [ARCHITECTURE](../ARCHITECTURE.md#remaining-risks).
