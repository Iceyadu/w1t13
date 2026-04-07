#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

API_BASE_URL="${API_BASE_URL:-}"
PASS=0
FAIL=0

green()  { printf "\033[32m%s\033[0m\n" "$*"; }
red()    { printf "\033[31m%s\033[0m\n" "$*"; }
yellow() { printf "\033[33m%s\033[0m\n" "$*"; }

banner() {
  echo ""
  echo "========================================"
  echo "  $1"
  echo "========================================"
  echo ""
}

wait_for_backend() {
  if [ -z "$API_BASE_URL" ]; then
    # Auto-detect common local ports used by this project/evaluators.
    for candidate in "http://localhost:8001" "http://localhost:8000"; do
      if curl -sf "$candidate/api/v1/health" > /dev/null 2>&1; then
        API_BASE_URL="$candidate"
        break
      fi
    done
    # Keep default fallback for messaging if still not detected.
    API_BASE_URL="${API_BASE_URL:-http://localhost:8001}"
  fi

  yellow "Waiting for backend at $API_BASE_URL/api/v1/health ..."
  for i in $(seq 1 30); do
    if curl -sf "$API_BASE_URL/api/v1/health" > /dev/null 2>&1; then
      green "Backend is ready."
      return 0
    fi
    sleep 2
  done
  red "Backend did not become ready in 60 seconds."
  return 1
}

run_pytest() {
  local test_path="$1"
  shift

  # Prefer local python when pytest is available.
  if python -c "import pytest" >/dev/null 2>&1; then
    python -m pytest "$test_path" -v --tb=short "$@"
    return $?
  fi

  # Fallback for CI/evaluator environments where host python lacks pytest.
  if command -v docker >/dev/null 2>&1; then
    yellow "Host python has no pytest; running tests inside backend container..."
    docker compose exec -T backend python -m pytest "/workspace/$test_path" -v --tb=short "$@"
    return $?
  fi

  red "pytest is unavailable (host + docker fallback)."
  return 127
}

run_unit_tests() {
  banner "Unit Tests"
  if [ -d "unit_tests" ]; then
    yellow "Running backend unit tests..."
    run_pytest unit_tests/backend/
    local exit_code=$?
    if [ $exit_code -eq 0 ]; then
      green "Unit tests passed."
      PASS=$((PASS + 1))
    else
      red "Unit tests failed (exit code $exit_code)."
      FAIL=$((FAIL + 1))
    fi
  else
    yellow "No unit_tests/ directory found. Skipping."
  fi
}

run_api_tests() {
  banner "API Tests"
  wait_for_backend

  if [ -d "API_tests" ]; then
    yellow "Running API tests against $API_BASE_URL ..."
    API_BASE_URL="$API_BASE_URL" run_pytest API_tests/
    local exit_code=$?
    if [ $exit_code -eq 0 ]; then
      green "API tests passed."
      PASS=$((PASS + 1))
    else
      red "API tests failed (exit code $exit_code)."
      FAIL=$((FAIL + 1))
    fi
  else
    yellow "No API_tests/ directory found. Skipping."
  fi
}

MODE="${1:-all}"

case "$MODE" in
  unit) run_unit_tests ;;
  api)  run_api_tests ;;
  all)  run_unit_tests; run_api_tests ;;
  *)    echo "Usage: $0 [unit|api|all]"; exit 1 ;;
esac

banner "Test Summary"
echo "Passed: $PASS"
if [ $FAIL -gt 0 ]; then
  red "Failed: $FAIL"
  exit 1
fi
green "All test suites passed."
exit 0
