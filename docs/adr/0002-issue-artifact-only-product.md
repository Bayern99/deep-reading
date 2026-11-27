[ English | [简体中文](0002-issue-artifact-only-product.zh-CN.md) ]

# One Issue Artifact Is the Product

**Status: accepted**

The product delivered to a reader is one portable Issue Artifact: a self-contained HTML publication compiled from one external issue workspace. The workspace provides the PDF, print evidence, reviewed bilingual content, routing, and editorial input. The tool repository supplies reusable instructions, rules, and code.

The Issue Artifact has an edition overview and immersive reading. The reader sees the publication, not a production console. LQA and certification reports remain beside the artifact in the external workspace.

## Decision

**Keep one product surface and one issue workflow.** The compiler writes one HTML artifact. Intermediate files and reports are working material, not additional products. The selected external issue root is the only source for issue-specific content.

## Considered options

- **A second interactive workbench for readers or operators:** rejected. It creates a separate product surface and exposes production state to readers.
- **A second compile path with different evidence and narrative rules:** rejected. Different routes can disagree about which content is authoritative and which quality rules apply.
- **Embed workspace manifests, LQA reports, or certification details in the Reader:** rejected. They are useful to the operator and distracting to the reader; the HTML remains a publication.
- **Keep dated issue data in the reusable tool package:** rejected. A release should not require a private or previously prepared issue to run. Each user supplies an external issue workspace.

## Consequences

- Authoritative product documents describe only the external issue workflow and the single Issue Artifact. They do not prescribe a second reader application.
- The user workflow is `prepare_issue` → review discovery and translations → finalize the issue inventory → `tracer_pipeline --issue-root` → HTML plus workspace reports. See [render/BUILD.md](../../render/BUILD.md).
- `make tracer ISSUE_ROOT=...` creates the reader artifact and LQA report. `make tracer-certify ISSUE_ROOT=...` additionally writes the seven-Oracle report for that issue.
- The HTML never embeds the issue PDF, translation inventory, raw evidence, or work reports. These stay in the external issue root.
- A source distribution is ready to reuse when it runs from a new external issue root without relying on bundled issue material.
