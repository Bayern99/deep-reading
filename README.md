# WSJ 深读

A bilingual WSJ reading system with two production paths: a deterministic whole-issue newspaper and a local editorial Studio that generates, verifies, versions and reopens individual article artifacts. Phase 1–7 implementations and their evidence are preserved. Runtime checks and remaining limits are recorded in [the governance record](docs/governance-2026-10-14.md).

## Start here

| Document | Authority |
|---|---|
| [FOUNDATION](FOUNDATION.md) | Long-lived product and content invariants |
| [ARCHITECTURE](ARCHITECTURE.md) | Actual modules, data flow, persistence and current limits |
| [DESIGN](DESIGN.md) | Visual canon and explicitly labeled design experiments |
| [GLOSSARY](GLOSSARY.md) | Shared domain terms; distinct from issue translation glossaries |
| [BUILD](render/BUILD.md) | Publishing, Studio operation and recovery commands |
| [Claim Provenance](docs/claim-provenance.md) | Evidence/semantic review required for new generated editorial publication; historical audits remain distinct |
| [Data and Git policy](docs/data-policy.md) | Protected data, generated outputs and safe Git handling |
| [Historical evidence](docs/history/README.md) | Dated investigations, prototypes and validation records |

Use current code and current documents together. Historical reports establish what was observed at their date; they do not certify today's model deployment or production readiness.

## Install

Run from the repository root. Python 3.11+ is the development target; governance was exercised with Python 3.14.7. Production requires only `lxml` beyond the standard library. No Node/npm runtime is required.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

The isolated environment avoids dependencies and configuration installed by a particular Coding Agent harness. Poppler/PyMuPDF and model services are needed for some historical extraction experiments, not for reopening saved artifacts or the offline test suite.

## Verify before changing anything

```bash
make test
make smoke
```

`make test` runs the unittest suites and the separate legacy content-gate assertions. `make smoke` copies production inputs into a temporary workspace, executes both real build commands and the local Studio HTTP routes, verifies existing artifacts, and removes the copy. It never resumes the production queue or calls a model. Current acceptance data is the preserved `2026-10-12` issue.

## Open the product

```bash
make studio ISSUE=2026-10-12 PORT=8788
```

Open `http://127.0.0.1:8788/reader` for saved articles and `/studio` for the source library, curation and queue. Reopening a saved article does not regenerate it. Starting Studio resumes pending/interrupted queue work; inspect `2026-10-12/editorial-artifacts/_queue.json` first if you only intend to browse. Run one Studio writer per checkout/issue.

For standalone outputs:

```bash
make build ISSUE=2026-10-12
make reader ISSUE=2026-10-12
```

The outputs are `2026-10-12/dist/index.html` (whole issue), `baseline.html` (internal comparison), and `editorial-reader.html` (saved-artifact Reader snapshot). The snapshot can reopen saved content offline; generation and queue controls require the live server. `make build` does not consume generated editorial artifacts. `make reader` does not rebuild the whole-issue newspaper. See [BUILD](render/BUILD.md) before generating new content.

## Repository map

```text
render/                    Production Python modules, styles, acceptance tests;
                           also labeled historical drivers (see ARCHITECTURE)
YYYY-MM-DD/                Issue source, translation provenance, assets, plans,
                           versioned artifacts, queue and historical evidence
docs/                      Current operating policy plus dated evidence
experiments/               Preserved independent experiments; not production
reference/hybrid-v3/       Accepted visual starting point
scripts/smoke.py            Isolated runtime acceptance command
```

Start code changes at the responsible module, not a historical issue builder:

- Content/alignment and factual provenance: `integrity_gate.py`, `source_model.py`, `canonical_builder.py`, `claim_provenance.py`.
- Whole issue: `build.py`, `issue.py`, `article.py`, `enhanced_render.py`, `text_treatment.py`, `layout.py`, `components.py`.
- Generated article: `editorial_publisher.py`, `model_provider.py`, `editorial_compiler.py`, `artifact_store.py`.
- Studio, source library and queue: `editorial_studio.py`, `generation_queue.py`.

## Model configuration

Browsing and tests need no credentials. Generation sends canonical article text to the selected endpoint and may incur provider charges. The [credential-free sample](.env.example) shows the portable OpenAI-compatible configuration; Python does not load `.env` automatically. Export values in your launching shell or source your ignored local file explicitly.

The complete `WSJ_LLM_ENDPOINT` and `WSJ_LLM_API_KEY` take precedence over local Harness registry settings unless an explicit `GenerationConfig` overrides them. Model inventory can also be read from `~/.pi/agent/models.json` or `~/.omp/agent/models.json`; neither file belongs in Git. Direct Anthropic generation uses `ANTHROPIC_API_KEY`. Registry fallback does not prove an endpoint or model is available.

## Protect the work

Keep `final.json`, OCR/translation provenance, verified images, plans and editorial artifact versions. New build snapshots, credentials and local environments are ignored; existing tracked deliveries remain tracked. Phase 5–7 code and artifacts were untracked when governance started; the local governance checkpoint includes their validated implementation and preserved evidence. Review that checkpoint before a release or remote publication.

The [data policy](docs/data-policy.md) defines backup and version-control treatment. Major refactors, important data deletion, history rewriting, merges, deployment and remote pushes need Jerry's approval.
