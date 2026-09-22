import secrets
from app.utils import receipt as rcpt


def receipt_still_usable(row, principal, annual_rate, months, loan_id, monthly_payment) -> bool:
    if row is None:
        return False
    if rcpt.utc_now() > rcpt.parse_iso(row["expires_at"]) and not row["consumed"]:
        return False
    if not secrets.compare_digest(
            rcpt.fingerprint(principal, annual_rate, months),
            row["fingerprint"]):
        return False
    stored_loan = row["loan_id"]
    if (stored_loan is None) != (loan_id is None) or stored_loan != loan_id:
        return False
    if monthly_payment != row["monthly_payment"]:
        return False
    return True


def mark_consumed(conn, receipt_id: int, now: str) -> None:
    from app.repositories import receipts
    conn.execute(
        "UPDATE precheck_receipts SET consumed=1, consumed_at=? WHERE id=?",
        (now, receipt_id),
    )
