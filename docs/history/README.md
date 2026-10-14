# Historical evidence

These files retain their original findings and dates. They explain earlier constraints and decisions; they do not define current implementation or deployment readiness. Current authority: [README](../../README.md), [FOUNDATION](../../FOUNDATION.md), [ARCHITECTURE](../../ARCHITECTURE.md), [DESIGN](../../DESIGN.md).

Everything dated lives here, so `docs/` above this directory holds only current policy: [data policy](../data-policy.md), [claim provenance](../claim-provenance.md) and the [domain convention](../agents/domain.md).

| Bundle | Use when |
|---|---|
| [Governance record](governance-2026-10-14.md), [browser evidence](browser-evidence-2026-10-14/) | Seeing what the Phase 5–7 governance pass changed, and its desktop/mobile captures |
| [Reconstruction brief](PROJECT_RECONSTRUCTION_BRIEF.md) | Understanding the original reboot diagnosis |
| [Recovery audit](RECOVERY_AUDIT.md) | Investigating early extraction and visual recovery gaps |
| [Code audit](audit-code.md), [data audit](audit-data.md), [documentation audit](audit-docs.md) | Tracing pre-compiler capability claims |
| [Architecture audit](audit-2026-10-13/A-ARCHITECTURE-AUDIT.md) | Understanding defects diagnosed before convergence |
| [Convergence delivery](convergence-2026-10-13/DELIVERY.md) | Reviewing the static renderer convergence and its evidence |
| [Research report](research-2026-10-14/REPORT.md), [Golden Baseline](research-2026-10-14/GOLDEN-BASELINE.md), [Experiment 0](research-2026-10-14/EXPERIMENT-0.md) | Working from the agent-native and claim-provenance research |
| [Audit matrix](AUDIT_MATRIX.md), [Pre-production report](PREPRODUCTION_REPORT.md), [Selection validation](SELECTION_VALIDATION_REPORT.md), [Asset pipeline](ASSET_PIPELINE_REPORT.md) | Tracing the October 13 pattern, planner and asset work |
| [Enhancement reports](ENHANCEMENT_REPORT.md) ([v3](ENHANCEMENT_REPORT_V3.md)), [E1-025 fixes](E1025_FIXES.md) | Reviewing the enhancement acceptance results and case fixes |
| [Opportunity benchmark](OPPORTUNITY_BENCHMARK.md), [Layout decision specs](LAYOUT_DECISION_SPECS.md) | Reusing the opportunity criteria and pattern decision rules |
| [Reference study](ref-study-2026-10-12/) | Reading the external SDK notes gathered before the Studio work |
| [AnyDoc evaluation](anydoc-eval.md), [TranslateGemma proof](translate-gemma-proof.md) | Considering a PDF extraction or translation engine change |

**Still current reference.** The Golden Baseline and Experiment 0 are dated evidence and remain the reference for the claim-provenance contract and for the reading capability that must be retained. Being filed here does not retire them.

**Where the archives are.** These reports moved here from `render/`; their historical drivers moved to [archive/render-experiments](../../archive/README.md), and the issue-local experiment bundles, legacy scripts and historical outputs moved under `2026-10-12/archive/`. Links inside these reports point at the new location when the target moved, and otherwise describe the tree as of the report's date.

`experiments/phase5-exp01/` is an independent, preserved experiment with its own compiler and schema. Production uses `render/editorial_compiler.py`. Do not synchronize the two compilers or treat experiment snapshots as active artifacts.
