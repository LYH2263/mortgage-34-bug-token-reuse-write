import json


def create(conn, *, code, kind, loan_id, payload, fingerprint, monthly_payment,
           result, expires_at, now) -> int:
    cur = conn.execute(
        "INSERT INTO precheck_receipts"
        "(code,kind,loan_id,input_json,fingerprint,monthly_payment,result_json,"
        "expires_at,created_at) VALUES (?,?,?,?,?,?,?,?,?)",
        (code, kind, loan_id,
         json.dumps(payload, ensure_ascii=False), fingerprint, monthly_payment,
         json.dumps(result, ensure_ascii=False), expires_at, now))
    conn.commit()
    return int(cur.lastrowid)


def get_by_code(conn, code: str) -> dict | None:
    row = conn.execute(
        "SELECT * FROM precheck_receipts WHERE code=?", (code,)).fetchone()
    return dict(row) if row else None


def claim(conn, receipt_id: int, now: str) -> bool:
    """原子认领回执。仅当尚未消费时成功，返回是否抢到。

    靠 consumed=0 条件保证并发双提交中只有一方能认领，
    即使前置校验因时序原因双双通过，这里也只放行一条。
    """
    cur = conn.execute(
        "UPDATE precheck_receipts SET consumed=1, consumed_at=? "
        "WHERE id=? AND consumed=0",
        (now, receipt_id))
    return (cur.rowcount or 0) == 1


def attach_run(conn, receipt_id: int, run_id: int) -> None:
    conn.execute(
        "UPDATE precheck_receipts SET run_id=? WHERE id=?",
        (run_id, receipt_id))
