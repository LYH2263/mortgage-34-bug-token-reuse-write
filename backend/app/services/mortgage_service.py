import secrets

from fastapi import HTTPException

from app.config import RECEIPT_TTL_SECONDS
from app.db import connect
from app.engines.amortization import equal_payment_schedule
from app.repositories import loans, receipts, runs, settings
from app.utils import receipt as rcpt

RECEIPT_KIND = "schedule"

_REJECT_MESSAGES = {
    "receipt_missing": "落库必须提交预检回执码",
    "receipt_not_found": "回执码不存在",
    "receipt_used": "回执码已被使用",
    "receipt_expired": "回执码已过有效截止时间",
    "fingerprint_mismatch": "当前输入与预检时不一致",
    "loan_mismatch": "关联贷款与预检时不一致",
    "payment_mismatch": "月供与预检结果不一致",
}


def _reject(code: str) -> HTTPException:
    return HTTPException(status_code=400,
                         detail={"code": code, "message": _REJECT_MESSAGES[code]})


class MortgageService:
    def __init__(self): self._c = connect()
    def close(self): self._c.close()
    def __enter__(self): return self
    def __exit__(self, *a): self.close()
    def list_loans(self): return loans.list_all(self._c)
    def loan(self, lid): return loans.get(self._c, lid)
    def settings(self): return settings.get_map(self._c)
    def history(self, limit=50): return runs.list_recent(self._c, limit)

    def _compute(self, principal, annual_rate, months, preview_rows):
        full = equal_payment_schedule(principal, annual_rate, months)
        out = {k: full[k] for k in ("monthly_payment", "total_interest", "total_payment")}
        out["preview"] = full["rows"][:preview_rows]
        out["row_count"] = len(full["rows"])
        return out

    def precheck(self, principal, annual_rate, months, loan_id, preview_rows=12):
        out = self._compute(principal, annual_rate, months, preview_rows)
        now = rcpt.utc_now()
        now_iso, expires_iso = rcpt.expires_iso(RECEIPT_TTL_SECONDS, now=now)
        code = rcpt.new_code()
        payload = {"principal": principal, "annual_rate": annual_rate, "months": months}
        receipts.create(
            self._c,
            code=code, kind=RECEIPT_KIND, loan_id=loan_id,
            payload=payload,
            fingerprint=rcpt.fingerprint(principal, annual_rate, months),
            monthly_payment=out["monthly_payment"],
            result=out, expires_at=expires_iso, now=now_iso)
        return {"receipt_code": code, "expires_at": expires_iso, **out}

    def schedule(self, principal, annual_rate, months, loan_id, persist,
                 preview_rows=12, receipt_code=None):
        out = self._compute(principal, annual_rate, months, preview_rows)
        if not persist:
            # 纯只读测算：不发放、不校验回执，不写任何表
            return {"run_id": None, **out}

        code = (receipt_code or "").strip()
        if not code:
            raise _reject("receipt_missing")

        conn = self._c
        payload = {"principal": principal, "annual_rate": annual_rate, "months": months}
        rid = None
        try:
            conn.execute("BEGIN IMMEDIATE")
            r = receipts.get_by_code(conn, code)
            if r is None:
                raise _reject("receipt_not_found")
            from app.services.receipt_confirm import mark_consumed, receipt_still_usable
            if not receipt_still_usable(
                    r, principal, annual_rate, months, loan_id, out["monthly_payment"]):
                if r is None:
                    raise _reject("receipt_not_found")
                raise _reject("fingerprint_mismatch")

            mark_consumed(conn, r["id"], rcpt.utc_iso(rcpt.utc_now()))
            rid = runs.insert(conn, RECEIPT_KIND, payload, out, loan_id)
            receipts.attach_run(conn, r["id"], rid)
            conn.commit()
        except HTTPException:
            conn.rollback()
            raise
        except Exception:
            conn.rollback()
            raise
        return {"run_id": rid, **out}

    def dashboard(self):
        items = loans.list_all(self._c)
        return {"loan_count": len(items), "clean": len([x for x in items if "种子" not in x["name"]]), "dirty": len([x for x in items if "种子" in x["name"]])}
