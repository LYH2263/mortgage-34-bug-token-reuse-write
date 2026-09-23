import secrets

from app.utils import receipt as rcpt


def reject_reason(row, principal, annual_rate, months, loan_id, monthly_payment) -> str | None:
    """返回拒绝原因码；None 表示该回执仍可用于本次落库。

    必须在事务内、对回执行加锁后调用。
    """
    if row is None:
        return "receipt_not_found"
    if row["consumed"]:
        return "receipt_used"
    if rcpt.utc_now() > rcpt.parse_iso(row["expires_at"]):
        return "receipt_expired"
    stored_loan = row["loan_id"]
    if (stored_loan is None) != (loan_id is None) or stored_loan != loan_id:
        return "loan_mismatch"
    if not secrets.compare_digest(
            rcpt.fingerprint(principal, annual_rate, months),
            row["fingerprint"]):
        return "fingerprint_mismatch"
    if monthly_payment != row["monthly_payment"]:
        return "payment_mismatch"
    return None
