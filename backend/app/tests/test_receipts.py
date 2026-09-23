import threading

from fastapi.testclient import TestClient

from app.db import connect
from app.main import app

BODY = {"principal": 800000, "annual_rate": 4.2, "months": 360}


def _client():
    return TestClient(app)


def _run_count():
    with connect() as c:
        return c.execute("SELECT COUNT(*) n FROM calc_runs").fetchone()["n"]


def _receipt_count():
    with connect() as c:
        return c.execute("SELECT COUNT(*) n FROM precheck_receipts").fetchone()["n"]


def _precheck(client, **overrides):
    body = {**BODY, **overrides}
    r = client.post("/api/schedule/precheck", json=body)
    assert r.status_code == 200, r.text
    return r.json()


def _persist(client, code, **overrides):
    body = {**BODY, "persist": True, "receipt_code": code, **overrides}
    return client.post("/api/schedule", json=body)


def test_happy_path_precheck_then_persist():
    with _client() as client:
        before = _run_count()
        pre = _precheck(client)
        assert pre["receipt_code"]
        assert pre["expires_at"]
        assert pre["monthly_payment"] > 0
        # 预检本身不落 calc_runs
        assert _run_count() == before

        r = _persist(client, pre["receipt_code"])
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["run_id"] is not None
        assert data["monthly_payment"] == pre["monthly_payment"]
        assert _run_count() == before + 1

        with connect() as c:
            row = c.execute("SELECT * FROM precheck_receipts WHERE code=?",
                            (pre["receipt_code"],)).fetchone()
            assert row["consumed"] == 1
            assert row["run_id"] == data["run_id"]
            assert row["consumed_at"]


def test_replay_rejected_without_extra_run():
    with _client() as client:
        pre = _precheck(client)
        assert _persist(client, pre["receipt_code"]).status_code == 200
        before = _run_count()

        r = _persist(client, pre["receipt_code"])
        assert r.status_code == 400
        assert r.json()["detail"]["code"] == "receipt_used"
        assert _run_count() == before


def test_missing_receipt_rejected():
    with _client() as client:
        before = _run_count()
        r = client.post("/api/schedule", json={**BODY, "persist": True})
        assert r.status_code == 400
        assert r.json()["detail"]["code"] == "receipt_missing"
        assert _run_count() == before


def test_blank_receipt_rejected():
    with _client() as client:
        r = client.post("/api/schedule",
                        json={**BODY, "persist": True, "receipt_code": "   "})
        assert r.status_code == 400
        assert r.json()["detail"]["code"] == "receipt_missing"


def test_unknown_receipt_rejected():
    with _client() as client:
        before = _run_count()
        r = _persist(client, "not-a-real-code")
        assert r.status_code == 400
        assert r.json()["detail"]["code"] == "receipt_not_found"
        assert _run_count() == before


def test_fingerprint_mismatch_rejected():
    with _client() as client:
        pre = _precheck(client)
        before = _run_count()
        r = _persist(client, pre["receipt_code"], principal=900000)
        assert r.status_code == 400
        assert r.json()["detail"]["code"] == "fingerprint_mismatch"
        assert _run_count() == before


def test_loan_mismatch_rejected():
    with _client() as client:
        pre = _precheck(client, loan_id=1)
        before = _run_count()
        r = _persist(client, pre["receipt_code"], loan_id=2)
        assert r.status_code == 400
        assert r.json()["detail"]["code"] == "loan_mismatch"
        assert _run_count() == before

        # null 与具体值也不允许互换；回执未被消费，仍可按原参数落库
        r2 = _persist(client, pre["receipt_code"], loan_id=1)
        assert r2.status_code == 200
        assert _run_count() == before + 1


def test_expired_receipt_rejected():
    with _client() as client:
        pre = _precheck(client)
        with connect() as c:
            c.execute("UPDATE precheck_receipts SET expires_at=? WHERE code=?",
                      ("2000-01-01T00:00:00+00:00", pre["receipt_code"]))
            c.commit()
        before = _run_count()

        r = _persist(client, pre["receipt_code"])
        assert r.status_code == 400
        assert r.json()["detail"]["code"] == "receipt_expired"
        assert _run_count() == before


def test_payment_tamper_rejected():
    with _client() as client:
        pre = _precheck(client)
        with connect() as c:
            c.execute("UPDATE precheck_receipts SET monthly_payment=0.01 WHERE code=?",
                      (pre["receipt_code"],))
            c.commit()
        before = _run_count()

        r = _persist(client, pre["receipt_code"])
        assert r.status_code == 400
        assert r.json()["detail"]["code"] == "payment_mismatch"
        assert _run_count() == before


def test_readonly_calc_needs_no_receipt_and_writes_nothing():
    with _client() as client:
        runs_before = _run_count()
        receipts_before = _receipt_count()
        r = client.post("/api/schedule",
                        json={**BODY, "persist": False, "preview_rows": 6})
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["run_id"] is None
        assert len(data["preview"]) == 6
        # 即使乱带回执码也被忽略
        r2 = client.post("/api/schedule",
                         json={**BODY, "persist": False, "receipt_code": "garbage"})
        assert r2.status_code == 200
        assert _run_count() == runs_before
        assert _receipt_count() == receipts_before


def test_concurrent_double_submit_single_win():
    with _client() as client:
        pre = _precheck(client)
        before = _run_count()
        barrier = threading.Barrier(2)
        results = []

        def worker():
            barrier.wait()
            with TestClient(app) as local:
                r = _persist(local, pre["receipt_code"])
            results.append(r.status_code)

        t1 = threading.Thread(target=worker)
        t2 = threading.Thread(target=worker)
        t1.start(); t2.start(); t1.join(); t2.join()

        assert sorted(results) == [200, 400]
        assert _run_count() == before + 1
