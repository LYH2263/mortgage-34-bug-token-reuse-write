import secrets
from app.utils import receipt as rcpt


def receipt_reject_reason(row, principal, annual_rate, months, loan_id,
                          monthly_payment) -> str | None:
    """返回 None 表示回执可用于落库，否则返回对应的拒绝原因码。"""
    if row is None:
        return "receipt_not_found"
    if row["consumed"]:
        return "receipt_used"
    if rcpt.utc_now() > rcpt.parse_iso(row["expires_at"]):
        return "receipt_expired"
    if not secrets.compare_digest(
            rcpt.fingerprint(principal, annual_rate, months),
            row["fingerprint"]):
        return "fingerprint_mismatch"
    stored_loan = row["loan_id"]
    if (stored_loan is None) != (loan_id is None) or stored_loan != loan_id:
        return "loan_mismatch"
    if monthly_payment != row["monthly_payment"]:
        return "payment_mismatch"
    return None
