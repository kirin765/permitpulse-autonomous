from __future__ import annotations

import time
from urllib.parse import urlparse

import requests
from django.conf import settings
from django.db import connection


def _supabase_db_url() -> str:
    return settings.__dict__.get("SUPABASE_DB_URL", "") or settings.__dict__.get("DATABASE_URL", "")


def _db_host(database_url: str) -> str:
    if not database_url:
        return ""
    parsed = urlparse(database_url)
    return parsed.hostname or ""


def _is_supabase_host(host: str) -> bool:
    return host.endswith(".supabase.co") or host.endswith(".supabase.com")


def check_db_connection() -> dict:
    database_url = _supabase_db_url()
    host = _db_host(database_url)
    configured = bool(database_url) and _is_supabase_host(host)
    if not configured:
        return {
            "configured": False,
            "connected": False,
            "host": host,
            "error": "Supabase DB URL is not configured",
        }

    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        return {
            "configured": True,
            "connected": True,
            "host": host,
            "error": "",
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "configured": True,
            "connected": False,
            "host": host,
            "error": str(exc),
        }


def check_rest_connection() -> dict:
    url = (settings.SUPABASE_URL or "").rstrip("/")
    key = settings.SUPABASE_SERVICE_ROLE_KEY or settings.SUPABASE_ANON_KEY
    configured = bool(url and key)
    if not configured:
        return {
            "configured": False,
            "reachable": False,
            "status_code": 0,
            "latency_ms": 0,
            "error": "Supabase REST URL/key is not configured",
        }

    try:
        started = time.perf_counter()
        response = requests.get(
            f"{url}/rest/v1/",
            headers={
                "apikey": key,
                "Authorization": f"Bearer {key}",
            },
            timeout=5,
        )
        elapsed_ms = int((time.perf_counter() - started) * 1000)

        # 200/401/404 all indicate network reachability to Supabase REST gateway.
        reachable = response.status_code < 500
        return {
            "configured": True,
            "reachable": reachable,
            "status_code": response.status_code,
            "latency_ms": elapsed_ms,
            "error": "" if reachable else f"Unexpected status: {response.status_code}",
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "configured": True,
            "reachable": False,
            "status_code": 0,
            "latency_ms": 0,
            "error": str(exc),
        }


def supabase_status_payload() -> dict:
    db = check_db_connection()
    rest = check_rest_connection()

    if not db["configured"] and not rest["configured"]:
        status = "not_configured"
    elif db["connected"] and rest["reachable"]:
        status = "connected"
    else:
        status = "degraded"

    return {
        "status": status,
        "db": db,
        "rest": rest,
    }
