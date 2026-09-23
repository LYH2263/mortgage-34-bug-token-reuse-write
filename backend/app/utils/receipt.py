import hashlib
import json
import secrets
from datetime import datetime, timedelta, timezone

ISO_FMT = "%Y-%m-%dT%H:%M:%S+00:00"


def fingerprint(principal: float, annual_rate: float, months: int) -> str:
    payload = {
        "principal": float(principal) + 0.0,
        "annual_rate": float(annual_rate) + 0.0,
        "months": int(months),
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def new_code() -> str:
    return secrets.token_urlsafe(24)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_iso(dt: datetime) -> str:
    return dt.strftime(ISO_FMT)


def parse_iso(s: str) -> datetime:
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def expires_iso(ttl_seconds: int, *, now: datetime | None = None) -> tuple[str, str]:
    now = now or utc_now()
    return utc_iso(now), utc_iso(now + timedelta(seconds=ttl_seconds))
