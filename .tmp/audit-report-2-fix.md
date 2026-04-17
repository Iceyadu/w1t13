# Recheck Results for `audit-report-2.md`

Date: 2026-04-17  
Type: Static-only verification  
Scope: Re-validated Section 5 severity findings plus Section 6-8 security/coverage deltas from `audit-report-2.md`.

## Overall Recheck Result

Previously reported Section 5 issues resolved: **0/8**  
Section 6 security partial-pass findings reconciled: **0/4**  
Section 7 tests/logging partial-pass findings reconciled: **0/3**  
Section 8 coverage-risk mappings reconciled: **0/5**  
Remaining unresolved items from that report: **8**

## A) Issues from Section 5

1) **Issue 5.1**  
**Title:** Backup restore extraction is not safely constrained  
**Previous status:** Fail  
**Recheck status:** Unresolved  
**Evidence:** `repo/backend/app/routers/backup.py:315`  
**Conclusion:** Archive extraction safety guardrails were not identified in the current snapshot.

2) **Issue 5.2**  
**Title:** Global idempotency policy documented as required but not enforced  
**Previous status:** Fail  
**Recheck status:** Unresolved  
**Evidence:** `docs/api-spec.md:13`, `repo/backend/app/middleware/idempotency.py:20`, `repo/backend/app/middleware/idempotency.py:33`  
**Conclusion:** Missing/invalid idempotency keys are still tolerated and no generalized persistence-replay layer is confirmed.

3) **Issue 5.3**  
**Title:** Optimistic locking contract is inconsistently strict  
**Previous status:** Partial Pass  
**Recheck status:** Unresolved  
**Evidence:** `docs/api-spec.md:14`, `repo/backend/app/routers/credits.py:147`  
**Conclusion:** Contract-level `If-Match` strictness remains inconsistent across mutation endpoints.

4) **Issue 5.4**  
**Title:** Backup cryptography claim and implementation metadata diverge  
**Previous status:** Partial Pass  
**Recheck status:** Unresolved  
**Evidence:** `docs/design.md:866`, `repo/backend/app/routers/backup.py:196`  
**Conclusion:** Algorithm naming/expectation mismatch persists.

5) **Issue 5.5**  
**Title:** Weak backup defaults remain active in deploy defaults  
**Previous status:** Partial Pass  
**Recheck status:** Unresolved  
**Evidence:** `repo/backend/app/config.py:28`, `repo/docker-compose.yml:32`  
**Conclusion:** Default passphrase fallback remains available at config and compose layers.

6) **Issue 5.6**  
**Title:** Offline key-derivation fallback uses static salt  
**Previous status:** Partial Pass  
**Recheck status:** Unresolved  
**Evidence:** `repo/frontend/src/services/offlineCache.ts:67`  
**Conclusion:** Static fallback salt path remains present.

7) **Issue 5.7**  
**Title:** Derived offline key persisted in browser session storage  
**Previous status:** Partial Pass  
**Recheck status:** Unresolved  
**Evidence:** `repo/frontend/src/stores/auth.ts:37`, `repo/frontend/src/stores/auth.ts:76`  
**Conclusion:** Derived key persistence behavior remains unchanged.

8) **Issue 5.8**  
**Title:** Service-worker strategy remains minimal for offline UX claims  
**Previous status:** Partial Pass  
**Recheck status:** Unresolved  
**Evidence:** `repo/frontend/public/sw.js:2`, `repo/frontend/public/sw.js:22`  
**Conclusion:** Static asset precache scope and runtime fetch strategy remain narrow.

## B) Section 6 — Security Review Summary

**6.1 Authentication/session controls**  
**Previous status:** Pass  
**Recheck status:** Maintained  
**Evidence:** `repo/backend/app/routers/auth.py`, `repo/backend/app/dependencies.py`  
**Conclusion:** No regressions identified in baseline token/role authentication flow.

**6.2 Authorization boundaries**  
**Previous status:** Partial Pass  
**Recheck status:** Unresolved  
**Evidence:** `repo/backend/app/routers/credits.py`, `docs/api-spec.md:14`  
**Conclusion:** Endpoint-level policy strictness remains uneven against documented requirements.

**6.3 Cryptography and key management**  
**Previous status:** Partial Pass  
**Recheck status:** Unresolved  
**Evidence:** `repo/backend/app/config.py:28`, `repo/backend/app/routers/backup.py:196`, `repo/frontend/src/stores/auth.ts:37`  
**Conclusion:** Backup/defaults and offline key persistence concerns remain.

**6.4 Integrity controls (idempotency/locking)**  
**Previous status:** Partial Pass  
**Recheck status:** Unresolved  
**Evidence:** `repo/backend/app/middleware/idempotency.py`, `repo/backend/app/routers/credits.py:147`  
**Conclusion:** Strict mandatory header and durable idempotency semantics remain incomplete.

## C) Section 7 — Tests and Logging Review

**7.1 Backend API testing depth for hardening cases**  
**Previous status:** Partial Pass  
**Recheck status:** Unresolved  
**Evidence:** `repo/API_tests/` (no explicit backup traversal tests identified)  
**Conclusion:** Security-hardening edge tests remain limited.

**7.2 Frontend/offline safety testing**  
**Previous status:** Partial Pass  
**Recheck status:** Unresolved  
**Evidence:** `repo/unit_tests/frontend/`  
**Conclusion:** No static evidence found for adversarial key-lifecycle/offline-storage threat tests.

**7.3 Logging/idempotency observability linkage**  
**Previous status:** Partial Pass  
**Recheck status:** Unresolved  
**Evidence:** `repo/backend/app/services/audit_service.py`, `repo/backend/app/middleware/idempotency.py`  
**Conclusion:** No clear global linkage guaranteeing idempotency replay semantics in audit context.

## D) Coverage Confirmations from Section 8

1) **Mandatory idempotency header contract tests**  
**Previous status:** Insufficient  
**Recheck status:** Unresolved  
**Evidence:** `docs/api-spec.md:13`, `repo/API_tests/`  
**Conclusion:** Missing/invalid idempotency-key rejection tests are still not evident.

2) **Mandatory If-Match contract tests**  
**Previous status:** Insufficient  
**Recheck status:** Unresolved  
**Evidence:** `docs/api-spec.md:14`, `repo/API_tests/`  
**Conclusion:** Coverage for required `If-Match` enforcement consistency remains incomplete.

3) **Backup archive safety tests**  
**Previous status:** Missing  
**Recheck status:** Unresolved  
**Evidence:** `repo/backend/app/routers/backup.py:315`, `repo/API_tests/`  
**Conclusion:** No traversal/unsafe extraction tests identified.

4) **Offline key persistence threat tests**  
**Previous status:** Missing  
**Recheck status:** Unresolved  
**Evidence:** `repo/frontend/src/stores/auth.ts:37`, `repo/unit_tests/frontend/`  
**Conclusion:** No tests found validating constrained key persistence behavior.

5) **Service-worker offline shell robustness tests**  
**Previous status:** Insufficient  
**Recheck status:** Unresolved  
**Evidence:** `repo/frontend/public/sw.js`, `repo/unit_tests/frontend/`  
**Conclusion:** Limited static evidence for route/offline shell robustness validation.

## Final Determination

Based on static evidence in this repository snapshot, all major findings from `audit-report-2.md` remain unresolved. Security and offline architecture foundations are present, but hardening and strict policy enforcement are still below acceptance threshold.
