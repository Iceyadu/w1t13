# HarborView Delivery Acceptance & Project Architecture Static Audit

## 1. Verdict
- **Overall conclusion: Partial Pass**
- Basis: Core full-stack architecture, role gates, encryption helpers, and broad API coverage exist, but there are multiple **Blocker/High** gaps in requirement-fit consistency (order creation authority), listing data isolation, idempotency enforcement depth, backup/restore hardening, and documentation/runtime parity.

## 2. Scope and Static Verification Boundary
- **Reviewed (static):**
  - Project docs/config/scripts: `repo/README.md`, `repo/docker-compose.yml`, `repo/run_tests.sh`, `docs/design.md`, `docs/api-spec.md`
  - Backend routing/auth/services/models: `repo/backend/app/**`
  - Frontend routing/offline/retry services: `repo/frontend/src/**`
  - Test suites and harness shape: `repo/API_tests/**`, `repo/unit_tests/**`
- **Not reviewed/executed:**
  - No runtime startup, no Docker run, no DB restore execution, no test execution.
- **Intentionally not executed:**
  - Throughput, concurrent conflict race behavior, actual pg_dump/pg_restore outcomes, browser rendering/UX.
- **Manual verification required (runtime-dependent):**
  - End-to-end offline replay conflict flows, backup/restore on real data, production hardening behavior under misconfiguration.

## 3. Repository / Requirement Mapping Summary
- **Prompt core goal (as implemented):** Offline-capable property operations portal (FastAPI + PostgreSQL + Vue) with role-based access, billing/order/listings/content modules, local backups, and auditability.
- **Mapped implementation areas:**
  - Auth/session/role access: `repo/backend/app/routers/auth.py`, `repo/backend/app/dependencies.py`
  - Object-level controls: `repo/backend/app/utils/ownership.py`, domain routers
  - Billing/payments/credits/reports: `repo/backend/app/routers/billing.py`, `payments.py`, `credits.py`, `reports.py`
  - Orders/listings/content/media: `repo/backend/app/routers/orders.py`, `listings.py`, `content.py`, `media.py`
  - Backup/retention/restore: `repo/backend/app/routers/backup.py`
  - Offline cache/retry: `repo/frontend/src/services/offlineCache.ts`, `retryQueue.ts`, `api.ts`
  - Tests: `repo/API_tests/*.py`, `repo/unit_tests/backend/*.py`

## 4. Section-by-section Review

### 1. Hard Gates

#### 1.1 Documentation and static verifiability
- **Conclusion: Partial Pass**
- **Rationale:** Documentation is substantial and test harnesses exist, but documented runtime entry points and configured ports/URLs are inconsistent and can mislead verification.
- **Evidence:**
  - README startup/service URLs assume `80/8000/5432`: `repo/README.md:49`, `repo/README.md:80`, `repo/README.md:84`
  - Compose defaults publish `8080/8001/5433`: `repo/docker-compose.yml:10`, `repo/docker-compose.yml:36`, `repo/docker-compose.yml:52`
  - Test runner probes `8001` then `8000`: `repo/run_tests.sh:26`
- **Manual verification note:** Docs-to-runtime mismatch should be resolved before acceptance sign-off.

#### 1.2 Material deviation from Prompt/spec intent
- **Conclusion: Fail**
- **Rationale:** Several spec-level behaviors are modeled but not enforced consistently: staff order creation path, resident listing property isolation, practical idempotency persistence, and backup safety/hardening.
- **Evidence:**
  - API spec states staff can create orders: `docs/api-spec.md:540`
  - `POST /orders` always resolves caller to resident profile and fails for non-resident staff: `repo/backend/app/routers/orders.py:121`
  - Resident listings filter by status only (not resident property context): `repo/backend/app/routers/listings.py:62`
  - Idempotency middleware only parses header into request state; no global replay storage: `repo/backend/app/middleware/idempotency.py:19`, `repo/backend/app/middleware/idempotency.py:30`

### 2. Delivery Completeness

#### 2.1 Core explicit requirements coverage
- **Conclusion: Partial Pass**
- **Rationale:** Most domain modules and endpoints are present, but implementation depth is uneven in cross-cutting guarantees (idempotency semantics, tenant scoping in some reads, restore safety).
- **Evidence (implemented):**
  - Broad module and router coverage: `repo/backend/app/main.py:99`
  - Encryption of resident contact fields wired in resident endpoints: `repo/backend/app/routers/residents.py:22`, `repo/backend/app/routers/residents.py:307`
  - Role guard dependency pattern is consistent: `repo/backend/app/dependencies.py:41`
- **Evidence (gaps):**
  - Idempotency record helpers exist but are unused in domain handlers: `repo/backend/app/middleware/idempotency.py:33`
  - Transition idempotency does not use request idempotency key; it keys only by target status: `repo/backend/app/routers/orders.py:242`

#### 2.2 End-to-end deliverable vs partial/demo
- **Conclusion: Partial Pass**
- **Rationale:** This is not a toy scaffold; however, migration/versioning discipline and some resilience/security paths remain below production acceptance.
- **Evidence:**
  - Extensive API tests exist: `repo/API_tests/test_service_orders.py`, `repo/API_tests/test_object_auth.py`
  - Unit tests exist for auth/encryption/core services: `repo/unit_tests/backend/test_auth_service.py`, `repo/unit_tests/backend/test_encryption_service.py`
  - Alembic configured but no migration revisions present: `repo/backend/alembic.ini`, `repo/backend/alembic/versions/` (empty)
  - Startup still uses `Base.metadata.create_all()`: `repo/backend/app/main.py:53`

### 3. Engineering and Architecture Quality

#### 3.1 Structure and module decomposition
- **Conclusion: Pass**
- **Rationale:** Backend/frontend layering is coherent, routers are organized by domain, and shared ownership helpers reduce repetition.
- **Evidence:**
  - Domain router registration is clear and complete: `repo/backend/app/main.py:99`
  - Ownership helper module centralizes access checks: `repo/backend/app/utils/ownership.py:32`

#### 3.2 Maintainability/extensibility
- **Conclusion: Partial Pass**
- **Rationale:** Code organization is maintainable, but duplicated per-router idempotency logic and docs/implementation drift increase long-term regression risk.
- **Evidence:**
  - Repeated optimistic-locking conflict handling across routers: `repo/backend/app/routers/users.py:120`, `repo/backend/app/routers/listings.py:158`, `repo/backend/app/routers/content.py:157`
  - API contract drift vs implementation behavior (order creation authority): `docs/api-spec.md:540`, `repo/backend/app/routers/orders.py:121`

### 4. Engineering Details and Professionalism

#### 4.1 Error handling/logging/validation/API design
- **Conclusion: Partial Pass**
- **Rationale:** Conflict and error envelopes are reasonably structured, but security-sensitive restore behavior and idempotency guarantees are under-specified in execution.
- **Evidence:**
  - Structured 409 conflict helpers used broadly: `repo/backend/app/utils/conflict.py`
  - Backup restore extracts archive using `tar.extractall(...)` without member path sanitization: `repo/backend/app/routers/backup.py:315`
  - Default/weak backup passphrase is allowed with warning only: `repo/backend/app/main.py:43`, `repo/backend/app/config.py:28`

#### 4.2 Product-grade vs demo
- **Conclusion: Partial Pass**
- **Rationale:** The system is close to product-grade in breadth, but still has acceptance-level blockers in safety and requirement congruence.
- **Evidence:**
  - Full role-aware frontend routes and backend APIs exist: `repo/frontend/src/router/index.ts:6`, `repo/backend/app/main.py:99`
  - Critical hardening gaps remain in backup extraction and strict idempotency semantics.

### 5. Prompt Understanding and Requirement Fit

#### 5.1 Business goal/constraints fit
- **Conclusion: Partial Pass**
- **Rationale:** The implementation demonstrates strong understanding of the operational domain, but some explicit behavioral promises are not fully honored in code.
- **Evidence:**
  - Offline cache + retry queue architecture implemented: `repo/frontend/src/services/offlineCache.ts:58`, `repo/frontend/src/services/retryQueue.ts:33`
  - Staff order-creation promise in API spec not met in route behavior: `docs/api-spec.md:540`, `repo/backend/app/routers/orders.py:121`
  - Resident listing scope not tied to resident property: `docs/design.md:75`, `repo/backend/app/routers/listings.py:62`

### 6. Aesthetics (frontend-only)

#### 6.1 Visual/interaction quality
- **Conclusion: Not Applicable (static-only)**
- **Rationale:** Frontend code exists but was not executed in browser for UI/UX validation.

## 5. Issues / Suggestions (Severity-Rated)

### Blocker

1. **Blocker — Order creation authorization behavior conflicts with documented contract**
- **Conclusion:** Fail
- **Evidence:**
  - API spec allows staff creation path: `docs/api-spec.md:540`
  - Implementation forces resident profile lookup for all callers: `repo/backend/app/routers/orders.py:121`
- **Impact:** Admin/manager workflows can fail at runtime despite documented support.
- **Minimum actionable fix:** Allow staff to specify/resolve target resident context explicitly while preserving resident self-service restrictions.

2. **Blocker — Backup restore archive extraction is vulnerable to unsafe path materialization**
- **Conclusion:** Fail
- **Evidence:** `tar.extractall(extract_dir)` on decrypted archive without safe member checks: `repo/backend/app/routers/backup.py:315`
- **Impact:** Crafted backup archive could overwrite files outside intended restore directory.
- **Minimum actionable fix:** Implement safe tar member validation (reject absolute paths and `..` traversal) before extraction.

3. **Blocker — Resident listing access not constrained to resident’s property**
- **Conclusion:** Fail
- **Evidence:**
  - Resident sees all `published` listings globally: `repo/backend/app/routers/listings.py:62`
  - Design intent is property-scoped resident experience: `docs/design.md:75`
- **Impact:** Cross-property data exposure risk.
- **Minimum actionable fix:** Resolve resident property via `Resident -> Unit -> Property` and filter listings by that property for resident callers.

### High

4. **High — Idempotency framework is only partially wired and not persisted across endpoints**
- **Conclusion:** Partial Pass
- **Evidence:**
  - Middleware records key on request state only: `repo/backend/app/middleware/idempotency.py:29`
  - Persistence helpers exist but are unused: `repo/backend/app/middleware/idempotency.py:33`
- **Impact:** Duplicate write replay behavior is inconsistent and route-specific.
- **Minimum actionable fix:** Centralize idempotency check/store on write endpoints using `idempotency_keys` table with endpoint+user semantics.

5. **High — Transition idempotency ignores request idempotency key semantics**
- **Conclusion:** Partial Pass
- **Evidence:** Transition replay logic only checks `(order_id, to_status)` milestone presence: `repo/backend/app/routers/orders.py:242`
- **Impact:** Distinct transition requests to same state can be conflated; auditability/retry semantics weaken.
- **Minimum actionable fix:** Track transition idempotency by explicit key and actor/request context.

6. **High — Documented runtime ports/URLs do not match compose defaults**
- **Conclusion:** Partial Pass
- **Evidence:** README URLs and compose published ports diverge: `repo/README.md:80`, `repo/docker-compose.yml:52`
- **Impact:** Deployment/test bring-up failures and false-negative health checks for evaluators.
- **Minimum actionable fix:** Align README/service URL docs with compose defaults or adjust compose to documented ports.

### Medium

7. **Medium — Migration discipline is incomplete for a mutable production schema**
- **Conclusion:** Partial Pass
- **Evidence:** Alembic scaffold exists with no migration revisions and `create_all` startup path remains primary: `repo/backend/alembic/versions/` (empty), `repo/backend/app/main.py:53`
- **Impact:** Schema drift risk across environments and weak rollback/change tracking.
- **Minimum actionable fix:** Introduce versioned Alembic revisions and gate startup on migration state.

8. **Medium — Backup crypto posture in code and docs is inconsistent**
- **Conclusion:** Partial Pass
- **Evidence:**
  - Design references AES-256 for backups: `docs/design.md:866`
  - Code records `Fernet-AES-128-CBC`: `repo/backend/app/routers/backup.py:196`
- **Impact:** Security posture ambiguity and compliance/reporting mismatch.
- **Minimum actionable fix:** Standardize cryptographic claim and implementation details in code and docs.

## 6. Security Review Summary

- **Authentication entry points: Pass**
  - Evidence: token issue/refresh/logout and role dependency are implemented (`repo/backend/app/routers/auth.py`, `repo/backend/app/dependencies.py`).

- **Route-level authorization: Partial Pass**
  - Evidence: broad `require_roles(...)` usage across sensitive routes.
  - Gap: behavior-contract mismatch on order creation path and resident listing scope.

- **Object-level authorization: Partial Pass**
  - Evidence: bill/payment/credit/order ownership checks exist (`repo/backend/app/utils/ownership.py`).
  - Gap: listing visibility for residents is not property-isolated.

- **Function-level authorization: Partial Pass**
  - Evidence: status transition role map exists (`repo/backend/app/routers/orders.py:29`).
  - Gap: idempotency semantics for transitions are weakly bound to request identity.

- **Admin/internal/debug protection: Partial Pass**
  - Evidence: backup/user/audit endpoints are role-gated.
  - Gap: backup restore extraction safety is insufficient.

## 7. Tests and Logging Review

- **Unit tests: Partial Pass**
  - Core auth/encryption/billing/order-state tests exist (`repo/unit_tests/backend/*.py`).
  - Gap: no unit-level hardening tests for backup archive member validation.

- **API/integration tests: Pass (breadth), Partial Pass (depth)**
  - Strong endpoint coverage in quantity (`repo/API_tests/*.py`).
  - Gaps remain for documented-vs-implemented contract checks (staff order creation, resident listing property isolation).

- **Logging categories/observability: Partial Pass**
  - Audit logging calls are common (`repo/backend/app/services/audit_service.py`, router `log_audit` calls).
  - Idempotency persistence/audit correlation is not uniformly enforced.

## 8. Test Coverage Assessment (Static Audit)

### 8.1 Test Overview
- **Unit tests exist:** Yes (`repo/unit_tests/backend/`, 5 functional test modules + fixtures).
- **API tests exist:** Yes (`repo/API_tests/`, 20+ modules).
- **Framework:** pytest + httpx.
- **Test runner:** `repo/run_tests.sh`.

### 8.2 Coverage Mapping Table

| Requirement / Risk Point | Mapped Test Case(s) | Coverage Assessment | Gap | Minimum Test Addition |
|---|---|---|---|---|
| Object-level auth for billing/payments/credits | `repo/API_tests/test_object_auth.py` | basically covered | Limited cross-tenant listing checks | Add resident cross-property listings assertions |
| Order state-machine and transitions | `repo/API_tests/test_service_orders.py` | sufficient | Transition idempotency key semantics not validated | Add replay tests keyed by explicit duplicated/different idempotency keys |
| Offline conflict/retry flows | `repo/API_tests/test_offline_conflicts.py` | partial | Browser/client queue replay not validated E2E | Add browser-level replay tests with queued mutations |
| Backup/restore integrity and safety | No explicit backup exploit/safety tests found | insufficient | No path traversal/safe extraction tests | Add unit/API tests with crafted tar members |
| Docs/runtime parity checks | None | missing | Port/URL mismatch can regress silently | Add smoke tests aligned to documented endpoints |

### 8.3 Final Coverage Judgment
- **Partial Pass**
- Coverage is broad for CRUD and many auth paths, but underweighted on hardening, contract consistency, and restore safety.

## 9. Final Notes
- This assessment is static-only and evidence-based.
- Primary acceptance blockers are: backup restore safety, contract mismatch in order creation authority, and listing data isolation scope.
- Runtime verification remains required for offline replay behavior, restore reliability, and production hardening outcomes.
