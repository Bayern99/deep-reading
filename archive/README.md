# Archived code

Historical, non-production code moved out of the working tree so that production
locations say what they are. It is kept as primary evidence of how the October 2026
pattern, planner, layout, extraction and case work was actually produced.

None of it is an entry point. `make build`, `make reader`, `make studio`, `make gate`,
`make test`, `make check` and `make smoke` do not use any of it.

## Where it lives

| Location | What is there |
|---|---|
| `archive/render-experiments/` | Drivers that used to sit in `render/`: the old plan renderer and validators, the prompted planner, layout/prototype/case builders, the stage CLI, the PyMuPDF continuation repair |
| `2026-10-12/archive/experiments/` | Named experiments with their own code or study notes: `gen-test/`, `cases/`, `ovis-test/` |
| `2026-10-12/archive/legacy-scripts/` | One-off issue builders and the earlier input assembly chain: `build_html.py`, `build_v2.py`–`build_v6.py`, `merge.py`, `assemble.py`, `trans-T*.py`, `seed_glossary.py`, `check_delivery.py` |
| `2026-10-12/archive/historical-outputs/` | Generated pages, screenshots, stage artifacts and deliveries: `test-pages/`, `auto-test/`, `layout-test/`, `blind5/`, `reboot-proof/`, `convergence-before/`, `review-evidence/`, `stages/`, the interior prototype archive, the pre-October-13 `final.json` backup |
| `2026-10-12/archive/pre-reboot-html/` | The pre-reboot hand-built newspaper versions |

The split rule is content, not location: a **driver** is code, an **experiment** pairs code or
study notes with its result, an **output** is generated and reproducible from a driver.

## Running one deliberately

```bash
PYTHONPATH=render:archive/render-experiments .venv/bin/python archive/render-experiments/<script>.py
```

The drivers compute the repository root as two levels above their own directory
(`archive/render-experiments/`), and the issue-local scripts compute the issue directory as two
levels above theirs (`2026-10-12/archive/legacy-scripts/`). Their read and write paths were updated
to the archived locations, with deliberate exceptions: `build_reboot_four.py` still writes
`2026-10-12/dist/reboot-four.html` beside the delivery it proofs, and `turn_page.py` plus
`assemble.py` rewrite the issue `final.json` by design. Treat the last two as content migrations,
not routine steps.

## Known limits

Several drivers were already unrunnable on this machine before they were archived, and stay that
way: `gen-test/pipeline*.py` hardcode a Linux checkout and model endpoints, `build_v2.py`–`
build_v6.py` write to `/home/hatch/...`, `trans-T1-*.py` and `trans-T2-runner.py` read
`~/workspace/...`, and `build_layout_test.py`/`run_auto_test.py` read scratch files under `/tmp`
and `/tmp/blind18.json`. Their paths describe the machine and date they were written for.

Dated reports that describe this work are indexed in [docs/history](../docs/history/README.md).
