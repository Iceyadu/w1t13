# HarborView Security, Offline, and Operations Static Audit (Pass 2)

## 1. Verdict
- **Overall conclusion: Partial Pass**
- Basis: The codebase demonstrates mature module coverage and many guardrails, but there are persistent **Blocker/High** quality risks around contract strictness, idempotency policy enforcement, backup crypto defaults, and offline-key handling posture.

## 2. Scope and Static Verification Boundary
- **Reviewed (static):**
  - API contract and design docs: `docs/api-spec.md`, `docs/design.md`
  - Backend auth/idempotency/backup/domain routers and models
  - Frontend auth/offline cache/retry/service worker code
  - Test inventory and focus distribution
- **Not reviewed/executed:**
  - No runtime execution, browser test run, Docker orchestration test, or live DB migration.

## 3. Repository / Requirement Mapping Summary
- **Security primitives mapped:** JWT auth, role guards, ownership helper, encrypted resident fields, offline encrypted cache.
- **Operational primitives mapped:** health checks, backup trigger/restore/retention, retry queue, API and unit test suites.
- **Contract sources:** OpenAPI-style spec and design doc used as static acceptance baseline.

## 4. Section-by-section Review

### 1. Hard Gates

#### 1.1 Contract adherence and strictness
- **Conclusion: Partial Pass**
- **Rationale:** Contracts are well documented, but strictness is not consistently enforced server-side.
- **Evidence:**
  - API spec marks `Idempotency-Key` required for all write operations: `docs/api-spec.md:13`
  - Middleware accepts missing/invalid idempotency keys and proceeds: `repo/backend/app/middleware/idempotency.py:20`, `repo/backend/app/middleware/idempotency.py:26`
  - `PUT /credits/{id}/approve` allows missing `If-Match` despite spec-wide requirement: `repo/backend/app/routers/credits.py:138`, `repo/backend/app/routers/credits.py:147`

#### 1.2 Material deviation from requirement intent
- **Conclusion: Fail**
- **Rationale:** Security and reliability intent is partially implemented but undercut by permissive defaults and inconsistent enforcement.
- **Evidence:**
  - Backup passphrase default persists in config and compose fallback: `repo/backend/app/config.py:28`, `repo/docker-compose.yml:32`
  - Backup algorithm claim differs between design and implementation metadata: `docs/design.md:866`, `repo/backend/app/routers/backup.py:196`
  - Idempotency storage model exists but is not integrated as a global write dedup layer: `repo/backend/app/models/audit.py:26`, `repo/backend/app/middleware/idempotency.py:33`

### 2. Delivery Completeness

#### 2.1 Security/offline requirement coverage
- **Conclusion: Partial Pass**
- **Rationale:** Core mechanisms are present, but several are not hardened to their documented standard.
- **Evidence (implemented):**
  - Resident PII encryption and role-based masking: `repo/backend/app/routers/residents.py:43`, `repo/backend/app/services/encryption_service.py:48`
  - Offline encrypted IndexedDB cache and queue stores: `repo/frontend/src/services/offlineCache.ts:58`
- **Evidence (gaps):**
  - Static fallback salt used when no salt is supplied: `repo/frontend/src/services/offlineCache.ts:67`
  - Exported offline derived key persisted in browser session storage: `repo/frontend/src/stores/auth.ts:37`

#### 2.2 End-to-end readiness
- **Conclusion: Partial Pass**
- **Rationale:** Broad backend API tests exist, but security-hardening and frontend offline behavior have limited direct verification evidence.
- **Evidence:**
  - Many API tests target backend auth/object access/order/billing: `repo/API_tests/test_auth.py`, `repo/API_tests/test_object_auth.py`, `repo/API_tests/test_service_orders.py`
  - No dedicated tests found for backup archive traversal safety or frontend key material handling.

### 3. Engineering and Architecture Quality

#### 3.1 Structure and separation
- **Conclusion: Pass**
- **Rationale:** Security and domain responsibilities are mostly separated cleanly between routers, dependencies, services, and helpers.

#### 3.2 Policy consistency
- **Conclusion: Partial Pass**
- **Rationale:** Policy is clear in docs, but operational code takes permissive shortcuts in critical areas.
- **Evidence:**
  - Strict header requirements in docs: `docs/api-spec.md:13`, `docs/api-spec.md:14`
  - Optional enforcement in some routes and middleware bypass for malformed keys.

### 4. Engineering Details and Professionalism

#### 4.1 Defensive coding and security posture
- **Conclusion: Partial Pass**
- **Rationale:** There is meaningful security effort, but defaults and extraction behavior remain high-risk.
- **Evidence:**
  - Default backup passphrase accepted with warning (not startup fail): `repo/backend/app/main.py:43`
  - Archive extraction path hardening absent: `repo/backend/app/routers/backup.py:315`

#### 4.2 Product-grade vs demo
- **Conclusion: Partial Pass**
- **Rationale:** Product-like breadth is evident, but acceptance-grade hardening policy is incomplete.

### 5. Prompt Understanding and Requirement Fit

#### 5.1 Operational reliability fit
- **Conclusion: Partial Pass**
- **Rationale:** Reliability features are present (retry queue, idempotency header propagation), yet server-side guarantees are not uniformly strict.
- **Evidence:**
  - Client always injects idempotency for writes: `repo/frontend/src/services/api.ts:18`
  - Server accepts missing keys and does not enforce reusable idempotency ledger globally.

## 5. Issues / Suggestions (Severity-Rated)

### Blocker

1. **Blocker — Backup restore extraction is not safely constrained**
- **Conclusion:** Fail
- **Evidence:** `repo/backend/app/routers/backup.py:315`
- **Impact:** Potential filesystem write outside restore target when processing crafted archives.
- **Minimum actionable fix:** Implement safe-member extraction checks and reject suspicious tar entries.

2. **Blocker — Global idempotency policy is documented as required but not enforced**
- **Conclusion:** Fail
- **Evidence:** `docs/api-spec.md:13`, `repo/backend/app/middleware/idempotency.py:20`, `repo/backend/app/middleware/idempotency.py:33`
- **Impact:** Duplicate write replay behavior can diverge by endpoint and client quality.
- **Minimum actionable fix:** Reject missing/invalid `Idempotency-Key` on write routes requiring it, and persist/replay responses via `idempotency_keys`.

### High

3. **High — Optimistic locking contract is inconsistently strict**
- **Conclusion:** Partial Pass
- **Evidence:** Spec requires `If-Match` on all PUT/PATCH (`docs/api-spec.md:14`), but credit approval only checks when header exists (`repo/backend/app/routers/credits.py:147`).
- **Impact:** Concurrent update safety can silently degrade on certain mutation paths.
- **Minimum actionable fix:** Make `If-Match` mandatory where contract requires it; return `428` when missing.

4. **High — Backup cryptography claim and implementation metadata diverge**
- **Conclusion:** Partial Pass
- **Evidence:** `docs/design.md:866` vs `repo/backend/app/routers/backup.py:196`
- **Impact:** Security posture ambiguity in audits/compliance and operator expectations.
- **Minimum actionable fix:** Align implementation, metadata, and docs to one explicit algorithm/mode statement.

5. **High — Weak backup defaults remain active in deploy defaults**
- **Conclusion:** Partial Pass
- **Evidence:** `repo/backend/app/config.py:28`, `repo/docker-compose.yml:32`
- **Impact:** Deployment can ship with predictable backup passphrase if not overridden.
- **Minimum actionable fix:** Fail startup when default passphrase is present in non-dev mode (or unconditionally for acceptance builds).

### Medium

6. **Medium — Offline key-derivation fallback uses static salt**
- **Conclusion:** Partial Pass
- **Evidence:** `repo/frontend/src/services/offlineCache.ts:67`
- **Impact:** Cross-user/device key separation relies only on password quality when salt is not customized.
- **Minimum actionable fix:** Use per-user/per-device persisted random salt; bind salt lifecycle to authenticated identity.

7. **Medium — Derived offline encryption key is persisted in browser session storage**
- **Conclusion:** Partial Pass
- **Evidence:** `repo/frontend/src/stores/auth.ts:37`, `repo/frontend/src/stores/auth.ts:76`
- **Impact:** XSS/session compromise risk window includes decrypt-capable key material.
- **Minimum actionable fix:** Limit key persistence to in-memory where possible; if persistence is required, wrap with additional local protection and CSP hardening.

8. **Medium — Service-worker strategy is minimal for offline UX claims**
- **Conclusion:** Partial Pass
- **Evidence:** `repo/frontend/public/sw.js:2`, `repo/frontend/public/sw.js:22`
- **Impact:** Offline shell resilience for non-root routes/assets may be uneven.
- **Minimum actionable fix:** Expand precache manifest and route-level SPA fallback strategy.

## 6. Security Review Summary

- **Authentication/session controls: Pass**
  - JWT issue/refresh/revocation pipeline exists (`repo/backend/app/routers/auth.py`).

- **Authorization boundaries: Partial Pass**
  - Role and ownership checks are widespread.
  - Policy strictness still varies by endpoint.

- **Cryptography and key management: Partial Pass**
  - PII encryption and offline AES-GCM are present.
  - Backup passphrase defaults and algorithm clarity remain weak.

- **Data integrity controls: Partial Pass**
  - Optimistic locking broadly used.
  - Contract-level enforcement is inconsistent in selected endpoints.

## 7. Tests and Logging Review

- **Backend API testing: Pass (breadth), Partial Pass (hardening depth)**
  - Many functional tests exist, especially for auth and object access.
  - Few explicit tests around security-hardening edge cases (backup extraction safety, strict header contract enforcement).

- **Frontend/offline testing: Partial Pass**
  - Frontend unit tests exist, but no static evidence of deep adversarial offline-key handling tests.

- **Audit/logging trail: Partial Pass**
  - Audit logging is present in many mutating routes.
  - Idempotency-to-audit correlation still not uniformly guaranteed.

## 8. Test Coverage Assessment (Static Audit)

### 8.1 Test Overview
- **Unit tests exist:** Yes (backend + frontend suites present).
- **API tests exist:** Yes (large coverage set under `repo/API_tests`).
- **Security-hardening niche tests:** Limited for backup/archive and strict contract assertions.

### 8.2 Coverage Mapping Table

| Requirement / Risk Point | Mapped Test Case(s) | Coverage Assessment | Gap | Minimum Test Addition |
|---|---|---|---|---|
| Auth/login/token flows | `repo/API_tests/test_auth.py` | sufficient | None major | Add token revocation race tests |
| Object-level access checks | `repo/API_tests/test_object_auth.py` | basically covered | Property-scoped listing visibility | Add cross-property resident listing tests |
| Idempotent write contract strictness | Partial implicit checks | insufficient | Missing mandatory-header rejection tests | Add API tests for missing/invalid `Idempotency-Key` and missing `If-Match` |
| Backup restore safety | none explicit | missing | No traversal safety tests | Add malicious tar member restore tests |
| Offline key handling | frontend unit tests exist but limited evidence | insufficient | No threat-mode key persistence tests | Add tests for key lifecycle and storage constraints |

### 8.3 Final Coverage Judgment
- **Partial Pass**
- Broad functional coverage does not yet equal hardened coverage for high-risk operational/security edges.

## 9. Final Notes
- This is a static-only pass focused on security/offline/operations consistency.
- Acceptance-critical gaps are concentrated in backup restore safety and strict policy enforcement.
- Manual runtime verification is still required for restore reliability, replay semantics, and browser offline behavior under failure modes.
