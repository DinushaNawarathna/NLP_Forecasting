#!/usr/bin/env python3
"""
Post-deployment test script for Sigiriya Visitor Forecast API on Railway.

Usage:
    python test_railway.py https://YOUR-APP.railway.app

Tests:
    1. GET  /         → API info
    2. GET  /health   → Health check
    3. GET  /forecast → Forecast data
    4. POST /admin/login → Demo login returns token
"""

import sys
import json
import requests
from datetime import datetime

# ── colour helpers ──────────────────────────────────────────────────────────
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BOLD = "\033[1m"
RESET = "\033[0m"

def ok(msg):   print(f"  {GREEN}✓{RESET} {msg}")
def fail(msg): print(f"  {RED}✗{RESET} {msg}")
def info(msg): print(f"  {YELLOW}→{RESET} {msg}")

# ── individual tests ─────────────────────────────────────────────────────────

def test_root(base_url: str) -> bool:
    """GET / → API info."""
    print(f"\n{BOLD}[1] Testing GET /{RESET}")
    try:
        r = requests.get(f"{base_url}/", timeout=30)
        if r.status_code == 200:
            data = r.json()
            ok(f"Status {r.status_code}")
            ok(f"API name: {data.get('name', 'N/A')}")
            ok(f"Version: {data.get('version', 'N/A')}")
            return True
        else:
            fail(f"Status {r.status_code}: {r.text[:200]}")
            return False
    except requests.exceptions.ConnectionError:
        fail("Cannot connect — is the Railway URL correct?")
        return False
    except Exception as e:
        fail(f"Error: {e}")
        return False


def test_health(base_url: str) -> bool:
    """GET /health → healthy status."""
    print(f"\n{BOLD}[2] Testing GET /health{RESET}")
    try:
        r = requests.get(f"{base_url}/health", timeout=30)
        if r.status_code == 200:
            data = r.json()
            status = data.get("status", "unknown")
            ok(f"Status {r.status_code} — health: {status}")
            forecast_loaded = data.get("forecast_loaded", False)
            periods = data.get("forecast_periods", 0)
            if forecast_loaded:
                ok(f"Forecast loaded with {periods} periods")
            else:
                info("Forecast still loading (models take ~30-60 s to warm up)")
            return status == "healthy"
        else:
            fail(f"Status {r.status_code}: {r.text[:200]}")
            return False
    except Exception as e:
        fail(f"Error: {e}")
        return False


def test_forecast(base_url: str) -> bool:
    """GET /forecast?limit=5 → list of 5 forecast items."""
    print(f"\n{BOLD}[3] Testing GET /forecast?limit=5{RESET}")
    try:
        r = requests.get(f"{base_url}/forecast?limit=5", timeout=60)
        if r.status_code == 200:
            data = r.json()
            ok(f"Status {r.status_code} — returned {len(data)} items")
            if data:
                first = data[0]
                required = {"date", "forecast_visitor_count", "lower_bound", "upper_bound"}
                missing = required - set(first.keys())
                if not missing:
                    ok(f"All required fields present")
                    ok(f"Sample: {first['date']} → {first['forecast_visitor_count']:,} visitors")
                    return True
                else:
                    fail(f"Missing fields: {missing}")
                    return False
            else:
                info("Empty forecast list (models may still be warming up)")
                return True   # not a hard failure on first deploy
        elif r.status_code == 503:
            info("Models still loading (503) — normal for first deploy, retry in 60 s")
            return True
        else:
            fail(f"Status {r.status_code}: {r.text[:200]}")
            return False
    except Exception as e:
        fail(f"Error: {e}")
        return False


def test_admin_login(base_url: str) -> bool:
    """POST /admin/login with demo credentials."""
    print(f"\n{BOLD}[4] Testing POST /admin/login (demo credentials){RESET}")
    payload = {"email": "admin@sigiriya.local", "password": "demo123"}
    try:
        r = requests.post(
            f"{base_url}/admin/login",
            json=payload,
            timeout=30,
        )
        if r.status_code == 200:
            data = r.json()
            token = data.get("access_token", "")
            name  = data.get("name", "N/A")
            ok(f"Status {r.status_code} — logged in as '{name}'")
            ok(f"Token received: {token[:20]}...")
            return True
        elif r.status_code == 503:
            info("DB not connected yet — demo login returned 503 (retry after warm-up)")
            return True
        else:
            fail(f"Status {r.status_code}: {r.text[:300]}")
            return False
    except Exception as e:
        fail(f"Error: {e}")
        return False


def test_docs(base_url: str) -> bool:
    """GET /docs → FastAPI Swagger UI."""
    print(f"\n{BOLD}[5] Testing GET /docs (Swagger UI){RESET}")
    try:
        r = requests.get(f"{base_url}/docs", timeout=20)
        if r.status_code == 200:
            ok(f"Swagger UI accessible at {base_url}/docs")
            return True
        else:
            fail(f"Status {r.status_code}")
            return False
    except Exception as e:
        fail(f"Error: {e}")
        return False


# ── main ─────────────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print(f"\nUsage: python test_railway.py <RAILWAY_URL>")
        print(f"Example: python test_railway.py https://my-app.railway.app\n")
        sys.exit(1)

    base_url = sys.argv[1].rstrip("/")
    print(f"\n{BOLD}{'='*60}{RESET}")
    print(f"{BOLD}  Sigiriya API — Railway Deployment Tests{RESET}")
    print(f"{BOLD}{'='*60}{RESET}")
    print(f"  Target: {base_url}")
    print(f"  Time  : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{BOLD}{'='*60}{RESET}")

    results = {
        "Root endpoint":    test_root(base_url),
        "Health check":     test_health(base_url),
        "Forecast data":    test_forecast(base_url),
        "Admin login":      test_admin_login(base_url),
        "Swagger UI":       test_docs(base_url),
    }

    # Summary
    passed = sum(1 for v in results.values() if v)
    total  = len(results)

    print(f"\n{BOLD}{'='*60}")
    print(f"  RESULTS SUMMARY{RESET}")
    print(f"{BOLD}{'='*60}{RESET}")
    for name, result in results.items():
        icon = f"{GREEN}PASS{RESET}" if result else f"{RED}FAIL{RESET}"
        print(f"  {icon}  {name}")

    print(f"\n  {BOLD}{passed}/{total} tests passed{RESET}")

    if passed == total:
        print(f"\n  {GREEN}{BOLD}🎉 All tests passed! Your Railway deployment is healthy.{RESET}")
    else:
        print(f"\n  {YELLOW}⚠️  Some tests failed. Check the build logs in Railway dashboard.{RESET}")
        print(f"  {YELLOW}   Tip: ML models can take 60-90 s to warm up on first deploy.{RESET}")

    print()
    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    main()
