# Recheck Results for `audit-report-1.md`

Date: 2026-04-17  
Type: Static-only verification  
Scope: Re-validated high-severity issue set, security summary deltas, and coverage-risk points from `audit-report-1.md`.

## Overall Recheck Result

Previously reported Blocker/High issues resolved: **0/6**  
Section 6 security partial-pass findings reconciled: **0/5**  
Section 7 test/logging partial-pass findings reconciled: **0/3**  
Remaining unresolved items from that report: **6**

## A) Issues from Section 5

1) **Issue 5.1**  
**Title:** Order creation authorization behavior conflicts with documented contract  
**Previous status:** Fail  
**Recheck status:** Unresolved  
**Evidence:** `docs/api-spec.md:540`, `repo/backend/app/routers/orders.py:121`  
**Conclusion:** Staff-capable create contract is still not consistently implemented; route still requires resident profile resolution.

2) **Issue 5.2**  
**Title:** Backup restore archive extraction is vulnerable to unsafe path materialization  
**Previous status:** Fail  
**Recheck status:** Unresolved  
**Evidence:** `repo/backend/app/routers/backup.py:315`  
**Conclusion:** Archive extraction still uses `extractall` without explicit path sanitization guardrails.

3) **Issue 5.3**  
**Title:** Resident listing access not constrained to resident property  
**Previous status:** Fail  
**Recheck status:** Unresolved  
**Evidence:** `repo/backend/app/routers/listings.py:62`, `repo/backend/app/models/resident.py:16`  
**Conclusion:** Resident listing filter remains `status == published` without resident property isolation enforcement.

4) **Issue 5.4**  
**Title:** Idempotency framework is only partially wired and not persisted across endpoints  
**Previous status:** Partial Pass  
**Recheck status:** Unresolved  
**Evidence:** `repo/backend/app/middleware/idempotency.py:29`, `repo/backend/app/middleware/idempotency.py:33`  
**Conclusion:** Middleware still captures request key only; no generalized check/store integration detected.

5) **Issue 5.5**  
**Title:** Transition idempotency ignores request idempotency key semantics  
**Previous status:** Partial Pass  
**Recheck status:** Unresolved  
**Evidence:** `repo/backend/app/routers/orders.py:242`  
**Conclusion:** Transition dedup still hinges on `order_id + to_status` milestone existence rather than explicit key replay.

6) **Issue 5.6**  
**Title:** Documentation/runtime port and URL mismatch  
**Previous status:** Partial Pass  
**Recheck status:** Unresolved  
**Evidence:** `repo/README.md:80`, `repo/docker-compose.yml:52`, `repo/run_tests.sh:26`  
**Conclusion:** Runtime defaults remain divergent from README/service URL guidance.

## B) Section 6 — Security Review Summary

**6.1 Authentication entry points**  
**Previous status:** Pass  
**Recheck status:** Maintained  
**Evidence:** `repo/backend/app/routers/auth.py`, `repo/backend/app/dependencies.py`  
**Conclusion:** Baseline auth token and role dependency mechanisms remain intact.

**6.2 Route-level authorization**  
**Previous status:** Partial Pass  
**Recheck status:** Unresolved  
**Evidence:** `repo/backend/app/routers/orders.py`, `repo/backend/app/routers/listings.py`  
**Conclusion:** Route gates exist, but key behavior constraints still diverge from stated access model.

**6.3 Object-level authorization**  
**Previous status:** Partial Pass  
**Recheck status:** Unresolved  
**Evidence:** `repo/backend/app/utils/ownership.py`, `repo/backend/app/routers/listings.py:62`  
**Conclusion:** Ownership controls are strong for billing domains but resident listing isolation remains broad.

**6.4 Function-level authorization**  
**Previous status:** Partial Pass  
**Recheck status:** Unresolved  
**Evidence:** `repo/backend/app/routers/orders.py:29`, `repo/backend/app/routers/orders.py:242`  
**Conclusion:** Transition role gates remain, but deterministic idempotent replay semantics are still weak.

**6.5 Admin/internal/debug protection**  
**Previous status:** Partial Pass  
**Recheck status:** Unresolved  
**Evidence:** `repo/backend/app/routers/backup.py:315`  
**Conclusion:** Admin route protection is present, but restore extraction safety remains a blocker.

## C) Section 7 — Tests and Logging Review

**7.1 Unit tests**  
**Previous status:** Partial Pass  
**Recheck status:** Unresolved  
**Evidence:** `repo/unit_tests/backend/test_auth_service.py`, `repo/unit_tests/backend/test_encryption_service.py`  
**Conclusion:** Unit coverage remains useful but still lacks dedicated safety tests for backup extraction/path traversal.

**7.2 API/integration tests**  
**Previous status:** Partial Pass  
**Recheck status:** Unresolved  
**Evidence:** `repo/API_tests/test_service_orders.py`, `repo/API_tests/test_object_auth.py`  
**Conclusion:** API coverage remains broad, but unresolved high-risk scenarios are still not explicitly asserted.

**7.3 Logging/idempotency observability**  
**Previous status:** Partial Pass  
**Recheck status:** Unresolved  
**Evidence:** `repo/backend/app/middleware/idempotency.py`, `repo/backend/app/services/audit_service.py`  
**Conclusion:** Audit events exist, but idempotency/audit coupling is still inconsistent across write paths.

## D) Coverage Confirmations from Section 8

1) **Resident property-scoped listing visibility coverage**  
**Previous status:** Missing  
**Recheck status:** Unresolved  
**Evidence:** `repo/API_tests/test_listings.py`, `repo/backend/app/routers/listings.py:62`  
**Conclusion:** No dedicated test found for resident cross-property listing denial/filtering.

2) **Staff order creation contract coverage**  
**Previous status:** Insufficient  
**Recheck status:** Unresolved  
**Evidence:** `repo/API_tests/test_orders.py`, `docs/api-spec.md:540`, `repo/backend/app/routers/orders.py:121`  
**Conclusion:** Tests do not reconcile/lock behavior against documented staff create permissions.

3) **Backup extraction hardening coverage**  
**Previous status:** Missing  
**Recheck status:** Unresolved  
**Evidence:** `repo/API_tests/` (no focused backup safety test), `repo/backend/app/routers/backup.py:315`  
**Conclusion:** No path traversal / unsafe archive member tests were identified.

## Final Determination

Based on static evidence in the current repository snapshot, no previously reported Blocker/High findings from `audit-report-1.md` are reconciled as fixed in this recheck. The project remains structurally strong but not acceptance-ready until those gaps are addressed.
