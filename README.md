# WSJ 深读

A bilingual WSJ reading system. The daily product is one portable Issue Artifact compiled from Primary Vector Signals through three-tier editorial composition, the LQA Funnel and seven Certification Oracles ([ADR 0001](docs/adr/0001-three-tier-editorial-composition.md), [ADR 0002](docs/adr/0002-issue-artifact-only-product.md)).

The Studio workbench, per-article Editorial Artifact store, generation queue and `claim-evidence-v1` sidecar are not the product. Dated evidence of that pipeline lives under [docs/history](docs/history/README.md).

## Start here

| Document | Authority |
|---|---|
| [FOUNDATION](FOUNDATION.md) | Long-lived product and content invariants |
| [ARCHITECTURE](ARCHITECTURE.md) | Actual modules, data flow and current limits |
| [DESIGN](DESIGN.md) | Visual canon of the Issue Artifact Reader |
| [GLOSSARY](GLOSSARY.md) | Shared domain terms; distinct from issue translation glossaries |
| [BUILD](render/BUILD.md) | Compile, LQA and Oracle commands |
| [Data and Git policy](docs/data-policy.md) | Protected data, generated outputs and safe Git handling |
| [Historical evidence](docs/history/README.md) | Dated investigations, including the superseded claim-provenance contract |

Use current code and current documents together. Historical reports establish what was observed at their date; they do not certify today's model deployment or a second issue.

## Install

Run from the repository root. Python 3.11+ is the development target. The Issue Artifact path needs `lxml`; real (non-`--fast`) compiles also need `fitz` (PyMuPDF) and `PIL`. No Node/npm runtime is required.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

The isolated environment avoids dependencies installed by a particular Coding Agent harness. Poppler and OCR services are not required to compile the pinned 2026-10-14 Issue Artifact.

The tracer CLI defaults to `/opt/homebrew/bin/python3` (`TRACER_PYTHON` overrides). The pilot dataset and print PDF are pinned outside this repository in `render/tracer/compose.py`.

## Verify before changing anything

```bash
make hooks           # once per checkout: install the tracked guardrails
make check           # tracer unit tests + --fast smoke
make tracer-certify  # Issue Artifact + LQA Funnel + Certification Oracles
```

See [data policy](docs/data-policy.md).

## Open the product

```bash
make tracer          # full-issue Issue Artifact + LQA report → /tmp
make tracer-certify  # ... + deterministic 7-Oracle certification
```

Open the HTML file. There is no Studio server. The Reader lives inside the Issue Artifact (`中文` / `EN` / `双语`, overview and immersive views).

Cloud / bot VM: [skills/wsj-deep-read/SKILL.md](skills/wsj-deep-read/SKILL.md).

## Repository map

```text
render/tracer/             Issue Artifact pipeline (the product)
render/tracer_pipeline.py  CLI entry
skills/wsj-deep-read/      Agent Skill wrapper
tests/                     Unittest suites for the Issue Artifact pipeline
YYYY-MM-DD/                Issue trees; 2026-10-12 is Studio-era evidence
docs/                      Current operating policy plus dated evidence
docs/adr/                  Product decisions (0001 composition, 0002 Issue Artifact only)
docs/history/              Dated investigations
archive/render-experiments/ Historical drivers; not entry points
experiments/               Preserved independent experiments; not production
reference/hybrid-v3/       Superseded visual starting point
```

Start code changes in `render/tracer/`. Frozen Studio-era runtime is git branch `archive/studio-phase1-7`; do not reintroduce it on `main`.

## Protect the work

Keep Primary Vector Signals, reviewed translations, verified chart crops and dated evidence. The print PDF is not in Git. New compile snapshots in `/tmp` or at the repo root are not source.

The [data policy](docs/data-policy.md) defines backup and version-control treatment. Major refactors, important data deletion, history rewriting, merges, deployment and remote pushes need Jerry's approval.
