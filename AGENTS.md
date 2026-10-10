# Agent Execution Guidelines & Workflow Protocol

This repository is an AI-managed software development environment. All AI agents operating in this workspace MUST follow this workflow protocol without exception.

---

## 1. Core Operating Principles

1. **User Is the Final Decision Maker**: The user has sole authority over product requirements, scope, features, major architectural choices, tech stack, security models, and project priorities. Never silently make decisions on behalf of the user.
2. **Never Git Commit or Git Push**: AI agents must NEVER run `git commit`, `git push`, or alter Git history. Git commits, staging, and pushing are strictly and exclusively the user's duty.
3. **Never Invent Requirements**: Do not fabricate features, APIs, database schemas, technologies, or constraints. If information is unknown, it MUST remain marked as `UNKNOWN` or `UNCONFIRMED`.
4. **Preserve User Uncertainty**: Maintain the user's certainty level. Clearly classify ideas into standardized categories:
   - **Confirmed Requirements**
   - **Ambiguous Requirements**
   - **Missing Information**
   - **Constraints**
   - **Technical Decisions**
   - **Proposed Features**
   - **Out-of-Scope Ideas**
   Never silently convert `Proposed` or `Assumption` into `Confirmed`.
5. **No Premature Implementation**: Do not write application source code while critical requirements and architectural decisions remain unresolved or unapproved.
6. **No Silent Scope Expansion**: Never add "nice to have" features or turn AI recommendations into commitments without explicit confirmation.
7. **Documentation Is Persistent Knowledge**: Treat documentation (`docs/*`) as the single source of truth. Synchronize documentation before and after implementation.
8. **Record Major Decisions**: Document all major architectural, database, infrastructure, and protocol decisions in `docs/DECISIONS.md` using the ADR format.
9. **Avoid Unnecessary Questions**: Infer answers safely from established conventions, existing code, and documentation. Only ask questions when the answer materially affects requirements, architecture, security, scope, or correctness.
10. **Identify Contradictions**: Proactively identify and flag contradictions between user requirements, documentation, and implementation.

---

## 2. Documentation Map & Responsibilities

| Document | Purpose & Responsibilities |
| :--- | :--- |
| `docs/PRD.md` | Product vision, problem statement, target users, user needs, goals, use cases, scope. |
| `docs/REQUIREMENTS.md` | Functional and non-functional requirements, status tracking (Confirmed, Proposed, Ambiguous). |
| `docs/TRD.md` | Technical requirements, constraints, runtime, performance, and infrastructure requirements. |
| `docs/ARCHITECTURE.md` | System topology, component boundaries, data flow, communication protocols, external dependencies. |
| `docs/API.md` | API contracts, endpoints, schemas, authentication, request/response formats, error codes. |
| `docs/DATABASE.md` | Data models, storage engines, schemas, relations, indexing, migrations, lifecycle. |
| `docs/SECURITY.md` | Threat model, authentication/authorization, data privacy, secret management, encryption. |
| `docs/ROADMAP.md` | Milestones, task lists, current progress, priorities, backlog. |
| `docs/DECISIONS.md` | Approved Architectural Decision Records (ADRs). |
| `docs/RISKS.md` | Known technical, security, scalability, and product risks with mitigations. |
| `docs/CHANGELOG.md` | Chronological record of notable project changes. |

---

## 3. Workflow Lifecycle

```
[User Input & Requirements]
              │
              ▼
[Classify & Update docs/*.md] ──(Requires User Confirmation)──► [User Clarifications]
              │
              ▼
   [Confirmed Requirements]
              │
              ▼
   [Implementation & Verification]
              │
              ▼
[Synchronize docs/ & Record ADRs]
```
