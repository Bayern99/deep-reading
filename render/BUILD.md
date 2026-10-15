# Daily publishing and local Studio operation

Run these commands from the repository root after [README setup](../README.md#install). Read [FOUNDATION](../FOUNDATION.md) and [DESIGN](../DESIGN.md) before building/restyling; read [ARCHITECTURE](../ARCHITECTURE.md) before changing contracts or persistence.

## Offline verification

```bash
make test
make smoke
make gate ISSUE=2026-10-12
```

The unittest suites cover static rendering/alignment, canonical compilation, providers, persisted artifacts, HTTP workflow and queue recovery. The separate `test_p1.py` uses custom assertions rather than unittest discovery; `make test` runs both. All permanent generation tests use local deterministic inputs/endpoints. The smoke command builds both real outputs and exercises HTTP on an isolated copy with its queue omitted, without model calls or source writes.

`make gate` audits `final.json` without editing it. Exit 1 means at least one BLOCK; exit 0 can still contain WARN. Confirm every WARN rather than treating a zero exit code as publication approval.

### Full-issue vertical tracer (2026-10-14 pilot)

```bash
/opt/homebrew/bin/python3 render/tracer_pipeline.py --mode full \
    --output /tmp/wsj-2026-10-14-full.html --gate-report /tmp/gate-report.json
```

Compiles the whole 86-item 2026-10-14 issue into one self-contained Issue Artifact
(~71 units: 8 Tier 1 flagships, 54 Tier 2 genre units, 9 Tier 3 compact units) and
runs the two-stage LQA funnel gate over all 1,257 bilingual units (<0.5s Stage 1).
The compact `gate-report.json` is written next to the output (or `--gate-report`)
and is never embedded in the reader HTML. `--mode tracer` keeps the five-unit pilot
slice; `--units id,...` filters to a subset (use `--fast` to skip PDF raster work);
`--fast` smoke runs need no `fitz`/`PIL`. Stage-2 findings are dispositions
(recorded / escalate), not rewrites: canonical text stays read-only.

## Whole-issue newspaper

```bash
make build ISSUE=2026-10-12
```

Inputs: issue `final.json`, `front.json`, `editorial-plans/`, verified images and the legacy global manifests under `render/`. Outputs: issue `dist/index.html`, internal `baseline.html` and `render-receipts.json`. No model invocation occurs. The baseline shares repairs and assets; it is not linked from the reader newspaper.

Only PASS entries that remain selected by curation are published. WARN/BLOCK entries remain in source, with review anchors rather than visible articles. Receipt errors such as `alignment_mismatch`, `en_tail_dropped`, unknown anchors, unsupported operations or stale digests must be repaired from verified evidence; do not bypass them.

For a design exploration using the same renderer:

```bash
.venv/bin/python render/build.py --issue 2026-10-12 \
  --plans-dir 2026-10-12/editorial-explorations \
  --output exploration.html --no-baseline
```

`--no-baseline` preserves the existing baseline. Use it for explorations after an ordinary build has produced the baseline; current CLI post-checks expect that file for planned articles.

## Stored-article Reader and Studio

```bash
make reader ISSUE=2026-10-12
make studio ISSUE=2026-10-12 PORT=8788
```

The export is issue `dist/editorial-reader.html`. The server binds `127.0.0.1`; open `/reader` or `/studio`. Both use the same embedded client. Source inspection is distinct from artifact reading. Static snapshots reopen saved versions offline; model generation, issue refresh and queue control need live HTTP.

Inspect `_queue.json` before starting Studio. Server startup and payload collection can initialize/recover the queue and resume pending work. Run only one writer per issue/checkout. A finished or failed article does not regenerate when opened; select a saved version or explicitly submit a generation request.

## Generate deliberately

Configure the provider in the launching shell. `.env.example` is a safe sample, not an automatically loaded configuration. Never put tokens into source, prompts, screenshots or Git. The complete `WSJ_LLM_ENDPOINT` is an OpenAI-compatible chat-completions URL, not merely a base URL. `WSJ_LLM_API_KEY` overrides the local Harness registry; explicit `GenerationConfig` endpoint/key-environment selection comes first. See [README](../README.md#model-configuration).

Studio supports model selection, curation recommendations, batch admission and explicit WARN confirmation. Inspect sources and recommendations, then enqueue the selected articles. BLOCK is rejected; a brief receives restrained treatment guidance. Successful compilation adds a version. Failed generation records its failure and preserves the prior active version.

The existing CLI can generate synchronously:

```bash
.venv/bin/python render/editorial_studio.py --issue 2026-10-12 \
  --enqueue E1-014 --model google-vertex/gemini-4-argon
```

This command makes real provider calls, processes the queue and currently implies WARN confirmation. It is suitable only after editorial review. Cancellation does not abort an already running network request. Failed-task retry keeps prior versions; forcing a new submission may duplicate model work.

New strict compilation checks copy/structure and [Claim Provenance](../docs/claim-provenance.md). Authored interventions (a `figure`, `aside`, `section`, `table`, `blockquote`, `svg` or `data-claim` block, with its heading, copy, labels and drawing) are reviewed as one unit; loose typography with no number and no quotation is inventoried without gating. Gated targets without host evidence stay `needs_review` and cannot become a new verified version. Diagnostic compilation (`strict=False`) retains the proposed content and findings for review. Host agents supply `evidence_records` to `compile_editorial_artifact` and `import_raw_generation`; HTML cannot approve itself. Missing semantic review is not sent back to the generating model for automatic approval. Historical versions remain readable under their original audits. Inspect Chinese/English at desktop and 390px separately before visual acceptance.

Run the offline seven-story experiment with a **new** evidence directory:

```bash
.venv/bin/python scripts/experiment0.py --output /tmp/wsj-experiment0-evidence
```

It checks nine pinned historical generations in memory, proves supported quotes/calculations/interpretation/SVGs through isolated compilation/import/HTTP delivery, and hashes the protected live issue before/after. It never starts the live queue. Existing Studio/queue generation has no host-evidence submission interface in this experiment; finish semantic review through the Python import seam. See [Experiment 0 results](../docs/history/research-2026-10-14/EXPERIMENT-0.md).

## Recovery

1. Stop Studio and other writers before copying the full issue artifact tree and queue to a backup outside Git.
2. Preserve `_index.json`, `_queue.json`, all version directories, `latest.json`, canonical snapshots, failed outputs and `final.json` together. A source-only backup cannot recreate model outputs.
3. Malformed queue JSON now stops with `Invalid persistent queue`; it is not replaced by an empty queue. Keep the damaged file for diagnosis and restore an intact backup after checking task status. Do not delete the queue to make startup succeed.
4. If index/latest metadata is inconsistent, inspect preserved version `artifact.json`/`compiled.html` and compiler audit before any restoration. There is no transactional repair command. Avoid overwriting source or silently renumbering versions.
5. Restart one writer. Pending tasks resume; interrupted tasks can be recognized as completed by timestamp or requeued. Inspect the resulting queue and active version.

## Next real issue

Obtain the original PDF and required extraction/translation tools, then produce and QA the next `final.json`, assets and `front.json`. The repository does not yet provide a complete upstream runner. Do not rerun the historical `assemble.py` over an accepted source.

Before publishing another date, resolve the currently shared manifests/curated derivations and the whole-issue CLI's 117-item assertion. Date discovery and canonical metadata have been generalized; cross-issue content/configuration isolation has not. See the bounded risks in [ARCHITECTURE](../ARCHITECTURE.md#remaining-risks-before-broader-usage).
