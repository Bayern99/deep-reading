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

Preserve the dated audit/convergence directories in place: their relative image and code links remain usable. Earlier reports under `render/`, issue-local `cases/`, `gen-test/`, `blind5/`, `auto-test/`, `layout-test/`, `test-pages/` and `reboot-proof/` are also historical evidence. Their location does not make them production entry points. See the module inventory in ARCHITECTURE before running a historical driver; some require old absolute paths or external model services.

`experiments/phase5-exp01/` is an independent, preserved experiment with its own compiler and schema. Production uses `render/editorial_compiler.py`. Do not synchronize the two compilers or treat experiment snapshots as active artifacts.
