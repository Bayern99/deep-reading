# Historical evidence

These files retain their original findings and dates. They explain earlier constraints and decisions; they do not define current implementation or deployment readiness. Current authority: [README](../../README.md), [FOUNDATION](../../FOUNDATION.md), [ARCHITECTURE](../../ARCHITECTURE.md), [DESIGN](../../DESIGN.md).

Everything dated lives here, so `docs/` above this directory holds only current policy: [data policy](../data-policy.md) and the [domain convention](../agents/domain.md).

| Bundle | Use when |
|---|---|
| [Claim provenance contract](claim-provenance.md) (superseded 2026-10-16) | Reading the Experiment 0 sidecar protocol ADR 0001/0002 rejected |
| [Governance record](governance-2026-10-14.md), [browser evidence](browser-evidence-2026-10-14/) | Seeing what the Phase 5–7 governance pass changed, and its desktop/mobile captures |
| [Pipeline continuity probe](pipeline-probe-2026-10-15.md) | Seeing which hops of the *old* PDF→Studio chain were proven, partial, blocked or untested. It does not describe the Issue Artifact vector path |
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

**Dated, not current authority.** Golden Baseline and Experiment 0 remain evidence of a reading capability that was measured, and of the sidecar contract that was later rejected. They do not define how an Issue Artifact is compiled or certified. Current authority: [README](../../README.md), [FOUNDATION](../../FOUNDATION.md), [ARCHITECTURE](../../ARCHITECTURE.md), [DESIGN](../../DESIGN.md), [ADR 0001](../adr/0001-three-tier-editorial-composition.md), [ADR 0002](../adr/0002-issue-artifact-only-product.md).

**Where the archives are.** These reports moved here from `render/`; their historical drivers moved to [archive/render-experiments](../../archive/README.md), and the issue-local experiment bundles, legacy scripts and historical outputs moved under `2026-10-12/archive/`.

`experiments/phase5-exp01/` is an independent, preserved experiment with its own compiler and schema. Current production compiles through `render/tracer/`. Do not treat experiment snapshots or `render/editorial_compiler.py` as active publication.
