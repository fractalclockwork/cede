# DESIGN.md (v1) -- Superseded

> **This document is superseded.** The authoritative architecture for
> CEDE is now `docs/DESIGN_SPECIFICATION.md` (the v2 spec, with stable
> section identifiers DS-1 through DS-18). For where the project is
> heading, see `docs/DEV_OP.md` (Part 2). For day-to-day operation, see
> `docs/USER_GUIDE.md` and (for deep hardware regression)
> `docs/DEV_OP.md` (Part 3).

## Where to look now

| You want to | Read |
|-------------|------|
| Understand the CEDE architecture, contracts, and invariants | [`docs/DESIGN_SPECIFICATION.md`](docs/DESIGN_SPECIFICATION.md) |
| Look up terms (CEDE + embedded) | [`docs/DESIGN_SPECIFICATION.md` Appendix A](docs/DESIGN_SPECIFICATION.md#appendix-a-glossary-reader-expansion) |
| Know what's coming next | [`docs/DEV_OP.md`](docs/DEV_OP.md) (Part 2) |
| Use CEDE day-to-day (build / deploy / validate / debug) | [`docs/USER_GUIDE.md`](docs/USER_GUIDE.md) |
| Run the deep release-grade hardware sweep | [`docs/DEV_OP.md`](docs/DEV_OP.md#part-3--hardware-validation) (Part 3) |
| Run the inner-loop hardware smoke | `make hw-smoke` (Docker rebuild + flash/validate; see USER_GUIDE §2.0) |

## Section mapping (v1 -> v2)

The v1 sections have direct successors in the v2 specification; cite
the v2 section in new work. Older external references that name a v1
section can be translated using this table.

| v1 (this doc) | v2 (`docs/DESIGN_SPECIFICATION.md`) |
|---------------|--------------------------------------|
| §1 Overview, three-tier architecture | DS-3 Architecture Overview |
| §2 Design Philosophy | DS-16 Design Principles |
| §3 High-Level System Architecture | DS-3 (mermaid) |
| §4 Roles and Responsibilities | DS-4 Roles and Responsibilities |
| §5 Communication Architecture | DS-7 Unified Workflow + DS-8 Transport Layer |
| §6 Docker-Based Toolchain Packaging | DS-6 Toolchain Containers |
| §7 Bus Architecture | DS-10.3 `i2c_matrix`, DS-14.2 (I2C bus speed) |
| §8 Serial Communication Protocol | DS-9.5 Serial Banner Format, DS-8.2 |
| §9 Bring-Up Test Plan ("Hello Lab") | DS-14 Staged Bootstrap, DS-18.3 Validation Applications |
| §9.1 `digest=` attestation | DS-9 Build Identity and Attestation |
| §10 Future Extensions | DS-17 Future Considerations |

## Why this document remains in the tree

The v1 doc is kept (rather than deleted) so that:

- External notes, issues, and PRs that link to `DESIGN.md` continue to
  resolve and land here.
- Readers who arrive at the repo root see an explicit pointer to the v2
  spec rather than a 404.
- The historical narrative (the v1 framing of the system) stays
  available in git for context, while the v2 spec carries the load for
  current contracts and invariants.

Do not add new design content here. Add it to the appropriate DS-* section
in [`docs/DESIGN_SPECIFICATION.md`](docs/DESIGN_SPECIFICATION.md).
