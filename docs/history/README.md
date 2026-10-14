# Historical evidence

These files retain their original findings and dates. They explain earlier constraints and decisions; they do not define current implementation or deployment readiness. Current authority: [README](../../README.md), [FOUNDATION](../../FOUNDATION.md), [ARCHITECTURE](../../ARCHITECTURE.md), [DESIGN](../../DESIGN.md).

| Evidence | Use when |
|---|---|
| [Reconstruction brief](PROJECT_RECONSTRUCTION_BRIEF.md) | Understanding the original reboot diagnosis |
| [Recovery audit](RECOVERY_AUDIT.md) | Investigating early extraction and visual recovery gaps |
| [Code audit](audit-code.md), [data audit](audit-data.md), [documentation audit](audit-docs.md) | Tracing pre-compiler capability claims |
| [AnyDoc evaluation](anydoc-eval.md) | Considering a PDF extraction engine change |
| [TranslateGemma proof](translate-gemma-proof.md) | Reviewing historical translation experiments |
| [October 13 architecture audit](../audit-2026-10-13/A-ARCHITECTURE-AUDIT.md) | Understanding defects diagnosed before convergence |
| [Convergence delivery](../convergence-2026-10-13/DELIVERY.md) | Reviewing the static renderer convergence and its evidence |
| [Audit matrix](AUDIT_MATRIX.md), [Pre-production report](PREPRODUCTION_REPORT.md), [Selection validation](SELECTION_VALIDATION_REPORT.md), [Asset pipeline](ASSET_PIPELINE_REPORT.md) | Tracing the October 13 pattern, planner and asset work |
| [Enhancement reports](ENHANCEMENT_REPORT.md) ([v3](ENHANCEMENT_REPORT_V3.md)), [E1-025 fixes](E1025_FIXES.md) | Reviewing the enhancement acceptance results and case fixes |
| [Opportunity benchmark](OPPORTUNITY_BENCHMARK.md), [Layout decision specs](LAYOUT_DECISION_SPECS.md) | Reusing the opportunity criteria and pattern decision rules |

These dated reports moved here from `render/`, and their historical drivers moved to `archive/render-experiments/`. Paths and links inside them describe the tree as of their date; `render/` now holds production modules only.

Preserve the dated audit/convergence directories in place: their relative image and code links remain usable. Earlier issue-local `cases/`, `gen-test/`, `blind5/`, `auto-test/`, `layout-test/`, `test-pages/` and `reboot-proof/` directories are also historical evidence. Their location does not make them production entry points. See the module inventory in ARCHITECTURE before running a historical driver; some require old absolute paths or external model services.

`experiments/phase5-exp01/` is an independent, preserved experiment with its own compiler and schema. Production uses `render/editorial_compiler.py`. Do not synchronize the two compilers or treat experiment snapshots as active artifacts.
