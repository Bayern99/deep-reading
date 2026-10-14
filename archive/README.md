# Archived render drivers

Historical, non-production scripts moved out of `render/` so that directory holds
only modules the two production paths import. They are kept as evidence of how the
October 2026 pattern, planner, layout and case work was actually produced.

None of these is an entry point. `make build`, `make reader`, `make studio`,
`make gate`, `make test` and `make smoke` do not use them.

| Script | What it was | Why it is here |
|---|---|---|
| `plan_render.py` | Earlier `component_plan`/`data_ref` renderer | Superseded by `enhanced_render.py` |
| `plan_adapter.py`, `plan_validate.py` | Old plan conversion and validation dialect | Not in the production import chain |
| `autonomous_planner.py` | Prompted planner with local inference | Used only by the archived auto-test runner |
| `orchestrate.py` | Hardcoded E1-025 outline and plan build | Case implementation, not a general orchestrator |
| `pipeline.py` | Stage-name CLI that ran integrity only | Superseded by `build.py` |
| `run_auto_test.py`, `run_blind5.py` | Planner batch runners and replay harnesses | Historical QA with their own PASS semantics |
| `build_layout_test.py`, `build_layout_configs.py`, `build_prototype.py`, `build_test_pages.py`, `build_reboot_four.py` | Test pages, prototypes and proof strips | Example generators, not product entry points |
| `turn_page.py` | Continuation recovery using PyMuPDF and fixed offsets | Depends on a source PDF that is not in the repository |

Their imports assume `render/` is on `sys.path`, and several contain absolute paths
from an earlier machine. To run one deliberately:

```bash
PYTHONPATH=render .venv/bin/python archive/render-experiments/<script>.py
```

Issue-local historical drivers (`2026-10-12/gen-test/`, `cases/`, `auto-test/`,
`layout-test/`, `blind5/`) stay where they are. The `gen-test/` pipelines import
`plan_render` and `build_test_pages` from this directory, so they need
`PYTHONPATH=render:archive/render-experiments`, and their hardcoded `/home/hatch/...`
paths mean they do not run on this machine as they stand. Dated reports that
describe them are in [docs/history](../docs/history/README.md).
