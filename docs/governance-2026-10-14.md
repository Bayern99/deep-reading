# Repository and architecture governance · 2026-10-14

## Result and scope

Preserve the validated Phase 1–7 implementation, make the real runtime navigable, establish a portable local development entry point, and record risks before actual usage testing. No visual redesign, upstream engine replacement, package migration or transactional-store rewrite was undertaken.

Checkpoint `f8ff92b` includes both the pre-existing uncommitted implementation/evidence and the governance changes. It was created on `governance/phase7-foundation`; at Jerry's request, that branch was renamed to `main`, the sole local branch for ongoing work. The older local `master` and `reboot/reconstruction-brief` names were removed after confirming their commits were ancestors of the checkpoint. All history is retained. No merge, deployment or remote push occurred.

## Main findings

- The starting branch was `master`, at `46529f2`, equal to its recorded `origin/master`. There were 23 modified tracked paths and 26 grouped untracked entries. Phase 5–7 production modules, acceptance tests and saved editorial artifacts were present only in the working tree.
- There are two real publishing paths: the deterministic whole-issue renderer, and canonical generation → compiler → versioned artifact store → Studio/Reader. The first does not read the generated artifact store. Neither command runs the entire upstream PDF/OCR/translation workflow.
- The PDF is missing. Historical input adapters rely on external translation scripts and old paths. `render/pipeline.py` executes integrity only; it is not a complete daily orchestrator.
- Historical documents mixed early absence claims with newer results. The old BUILD_SPEC described absolute paths, a fixed input count and an outdated priority-group reader. The root lacked a project entry point and current architecture reference.
- Production still depends on one image in `2026-10-12/cases/assets/`. Historical directories cannot be deleted or moved merely because they contain experiments.
- Git had 34 commits, 1,847 tracked files, approximately 152 MiB of objects, and approximately 226 MB of non-cache working files at initial measurement. HTML/images/ZIP evidence dominate storage; largest observed file/blob was about 5.2 MB. No large-file/history migration was justified.

## Changes actually made

| Area | Governance |
|---|---|
| Structure | Archived seven root historical reports under `docs/history/`, preserving their bodies with dated-status notices; retained code/data/evidence paths and added a historical index. |
| Documents | Added README, actual ARCHITECTURE, domain GLOSSARY and data policy. Updated FOUNDATION to retain long-lived principles, clarified DESIGN scope and corrected contradictory body sizes/digest treatment. Replaced stale BUILD_SPEC and consolidated operations/recovery in BUILD. |
| Agent entry | Updated AGENTS with short conditional pointers, root commands, data protection, single-writer queue behavior and verification expectations. |
| Git policy | Added credential/environment/build-cache ignore rules and explicit text/binary attributes. New `dist/` snapshots are ignored; already tracked deliveries and all source/artifact evidence remain intact. |
| Development | Added pinned `lxml==6.1.1`, isolated `.venv`, credential-free `.env.example`, root Makefile commands and `scripts/smoke.py`. No shared Python environment was modified. |
| Date metadata | Canonical dates follow the selected issue rather than always labeling articles October 12. Source copy and digest remain unchanged. |
| Queue | Invalid queue JSON or a non-list task collection raises an explicit error; existing damaged data is not silently treated as an empty queue. |
| Artifact paths | Reject directory-bearing article identifiers and invalid/unregistered version identifiers before activation. |
| Provider configuration | Explicit endpoint/key environment settings override Harness registry fallback for OpenAI-compatible generation. Tested through an actual local HTTP endpoint. |
| Portable gate | Integrity CLI takes an explicit final.json path and no longer defaults to an absent `/home/hatch` path. |
| Test hygiene | Removed the permanent suite's write to the real historical Reader export and its incidental file-size assertion. Isolated runtime smoke owns real export verification. |
| Small corrections | Fixed reversed `--no-baseline` help and replaced the source-model doc's unavailable `/tmp/kit` reference with current repository contracts. |

The four behavioral fixes each had a failing-before/passing-after regression. No source translation was edited, no article version was replaced, and no historical experiment compiler was migrated into production.

## Verification evidence

| Check | Observed result |
|---|---|
| Before governance | 13 unittest cases passed; 16 legacy content-gate assertions passed. |
| After governance (`make test`) | 17 unittest cases passed; all 16 legacy assertions passed. Four new regression cases cover dates, queue preservation, artifact path confinement and provider configuration. |
| Isolated dependencies | Python 3.14.7, lxml 6.1.1; `.venv/bin/python -m pip check`: no broken requirements. The pre-existing shared Python environment had an unrelated wheel/packaging issue; it was left unchanged. |
| Actual builds and HTTP (`scripts/smoke.py --issue 2026-10-12 --keep`) | Both real build commands and Studio/Reader HTTP routes passed in a copied workspace. 117 source items, 92 whole-issue published entries, five plans, eight stored article identities and 11 saved versions. No model calls. |
| Real content gate (`make gate`) | 113 PASS / 4 WARN / 0 BLOCK; unchanged WARNs are E1-004, E1-007, E3-002 and E3-005, each an unconfirmed continuation. |
| Browser | Chromium: whole newspaper and saved-article Reader at 1440px/390px, no document overflow; CN/EN controls worked. Newspaper showed 92 article elements and 18 loaded images. Saved-version selection v3→v1 and canonical inspector worked. Curation/source library and empty isolated queue displayed. |
| Git integrity | `git fsck --full` succeeded without diagnostics. |
| Credentials | Common private-key/token/literal-key scan found no candidates in the initial worktree or 425 unique historical text blobs. This is format-based evidence, not proof that every possible credential format is absent. No credentials were printed. |
| Preservation | Byte hashes checked across existing issue source, assets, artifact tree, experiments and reference evidence; no protected content changes. macOS `.DS_Store` metadata is excluded from this guarantee. `final.json` SHA-256 remains `00fa35e8f5a9bc164da3dae3af41c6b659c1e2c609d1e535729a6fbb3efd5782`. |
| Documentation | Current entry documents and newly archived root reports have valid local file links. Historical evidence intentionally retains its original unavailable external-machine references. |

Browser images: [newspaper desktop](governance-2026-10-14/newspaper-desktop.png), [newspaper mobile](governance-2026-10-14/newspaper-mobile.png), [Reader desktop](governance-2026-10-14/reader-desktop.png), [Reader mobile](governance-2026-10-14/reader-mobile.png).

The first isolated smoke exposed a missing copied `cases/assets/` dependency. The copy scope was corrected; the production asset and its historical location were preserved. Verification used a temporary queue rather than resuming the real queue. No live external model, full PDF extraction, new-date publication, Safari or Firefox run was performed.

## Remaining work worth prioritizing

1. **Second real issue and configuration isolation.** The whole-issue CLI still asserts 117 inputs. Global curation/images/alignment/asset/derived records reuse local article IDs and can contaminate another issue. Resolve those together before claiming daily reproducibility.
2. **Artifact persistence.** Store writes/index promotion/version allocation are not transactional or safe across multiple processes. Use one writer and stopped-writer backups until a bounded storage change is designed. Timestamp-only queue recovery and cancellation semantics also merit a precise task/version contract.
3. **Source drift.** Saved versions remain readable, but Studio does not flag a source-digest change when deciding that an article is generated. The most recent canonical snapshot is not a per-version source archive.
4. **Security before sharing.** The server is loopback-only but unauthenticated; mutating routes have no origin policy. Compiler verification retains short scripts, confirmed with a harmless probe. Shadow DOM is not a privilege sandbox. Define and test an HTML/CSS/script policy before exposing the service or treating arbitrary output as safe.
5. **Editorial and design approval.** Narrative exactness does not establish the factual accuracy of unrestricted added labels/graphics. The current publishing prompt's palette/font prescription differs from the static DESIGN canon. Review that deliberately; governance did not restyle accepted artifacts.
6. **Upstream inputs.** Restore the PDF and the extraction/translation tools needed to produce a new accepted final source. Keep the four continuation WARNs unresolved until source evidence supports disposition.

These are bounded follow-up recommendations, not silently performed refactors. Current protected data and established reading behavior remain available for local usage tests.
