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


def claim(conn, receipt_id: int, now: str) -> int:
    # 原子占位：仅当回执尚未被消费时才置位，返回实际影响行数（0 表示已被抢走）。
    cur = conn.execute(
        "UPDATE precheck_receipts SET consumed=1, consumed_at=?"
        " WHERE id=? AND consumed=0",
        (now, receipt_id))
    return cur.rowcount


def attach_run(conn, receipt_id: int, run_id: int) -> None:
    conn.execute(
        "UPDATE precheck_receipts SET run_id=? WHERE id=?",
        (run_id, receipt_id))
