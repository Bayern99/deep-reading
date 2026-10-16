# Issue Artifact is the only product; the Studio pipeline is archived off main

Status: accepted

The daily product is a single portable Issue Artifact compiled from primary PDF vector/font signals through three-tier editorial composition, paragraph-scoped verification, the LQA funnel and 7-Oracle certification (ADR 0001). The earlier Studio methodology — secondary crops and OCR, `final.json` assembly, Integrity Gate as a daily door, Canonical Source sidecars, per-article Editorial Artifacts, ArtifactStore, the generation queue, and the local Studio HTTP workbench — is not a second product, not an internal baseline, and not a `main` entry point.

Runnable Studio-era code and issue data may exist only on a frozen Git branch / worktree (for example `archive/studio-phase1-7`). Dated evidence on `main` (`docs/history/`, this ADR, ADR 0001) explains why that pipeline was rejected. Existing `archive/` trees on `main` stay as already-filed evidence; they are not a place to keep a working Studio.

The Studio-era runtime was removed from `main` after Jerry's approval. Recover it from git branch `archive/studio-phase1-7` (`94638a2`). This ADR does not authorize rewriting Git history.

## Considered Options

- **Dual path: Issue Artifact daily, Studio preserved as a second production path.** Rejected. The two pipelines encode incompatible methodologies (lossy secondary data and sidecar evidence vs primary vectors and inline verification). Documenting both as current re-litigates a closed decision.
- **Keep `make build` / Integrity Gate as an internal baseline brand.** Rejected. A named baseline on `main` keeps the old chain as a product surface.
- **Move the runnable tree into `archive/` on `main`.** Rejected. `main` would still carry a working Studio and invite agents to run it.
- **Delete the old chain from Git history in the documentation pass.** Rejected. History rewriting remains a separate, Jerry-approved operation. The runtime cut on `main` keeps the objects reachable from `archive/studio-phase1-7`.

## Consequences

- Authoritative docs (`README`, `ARCHITECTURE`, `FOUNDATION`, `DESIGN`, `GLOSSARY`, `render/BUILD.md`, `AGENTS.md`) describe only the Issue Artifact pipeline.
- Product commands are `make tracer` / `make tracer-certify` / `make check`. `make studio`, `make reader`, `make build`, and `make gate` exist only on `archive/studio-phase1-7`.
- Studio-era remaining-risks (queue crash, store concurrency, Studio HTML sanitizer, loopback API auth) do not bind the Issue Artifact.
