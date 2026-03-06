# AgentBond Product Roadmap

Last updated: 2026-03-02

## Product Goals
- Deliver a usable operator and user workflow end to end.
- Keep policy enforcement deterministic and explainable.
- Make claims reliable, observable, and fast to resolve.
- Reach production-ready deployment with clear operations.

## Phase 1 - Usable MVP (0-4 Weeks)
- One-command local startup for backend + frontend.
- Guided onboarding flow for operator registration, policy setup, and staking.
- End-to-end run flow from UI: create run, see verdict, submit claim.
- Strong empty/loading/error states across dashboard pages.
- Seed and demo scripts that produce realistic sample data.

## Phase 2 - Reliability and Trust (4-8 Weeks)
- Public runs explorer with filters for agent, verdict, and claim status.
- Two baseline deterministic policies:
  - Tool whitelist policy.
  - Value cap policy.
- Claim lifecycle hardening: retries, idempotency, and clear failure reasons.
- Webhook reliability: signed payload verification docs + delivery history UX.
- Core metrics: run latency, verification latency, claim resolution time.

## Phase 3 - Production Readiness (8-12 Weeks)
- Deployment hardening: environment validation, backup strategy, and rollback plan.
- Operational dashboards for API health, webhook failures, and queue backlogs.
- Security pass: endpoint auth review, rate-limit tuning, and dependency updates.
- Pilot rollout with 2-3 operators and structured feedback loop.
- Mainnet readiness checklist and release criteria.

## Milestones (Deliverables + Acceptance Criteria)

**M1 - Usable Core Workflow**
- Deliverable: onboarding + run + claim flow works from the frontend without manual DB edits.
- Deliverable: demo script produces pass/fail runs and at least one claim.
- Acceptance: fresh setup to first run in under 10 minutes on a clean machine.
- Acceptance: at least 90% frontend route test pass for Dashboard, Runs, Claims, Operator flows.

**M2 - Deterministic Policy Enforcement**
- Deliverable: baseline policies are enforced consistently in API and UI.
- Deliverable: violation reason codes are attached to runs and visible in run details.
- Acceptance: deterministic policy tests pass for both pass and fail paths.
- Acceptance: policy replay endpoint returns same verdict for same input.

**M3 - Reliable Claims and Webhooks**
- Deliverable: claim submission, verification, and resolution are robust under retries.
- Deliverable: webhook deliveries are signed, logged, and visible in operator history.
- Acceptance: claim status transitions are valid and auditable for all cases.
- Acceptance: webhook retry behavior is observable and documented.

**M4 - Production Rollout Readiness**
- Deliverable: monitoring dashboards and operational runbook are complete.
- Deliverable: pilot report with issues found, fixes shipped, and remaining risks.
- Acceptance: deploy and rollback can be executed from documented steps.
- Acceptance: all critical test suites pass in CI before release.
