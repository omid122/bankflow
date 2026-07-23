import os

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test_bankflow.db")
    monkeypatch.setenv("BANKFLOW_DB_PATH", db_path)

    # Reload the app module fresh so it picks up the temp DB path and
    # starts with a clean, isolated database for every test.
    import importlib
    import src.main as main_module

    importlib.reload(main_module)
    return TestClient(main_module.app)


def personal_payload(**overrides):
    payload = {
        "customerId": "C-1001",
        "amount": 400_000_000,
        "phone": "09121234567",
        "loanType": "PERSONAL",
        "monthlyIncome": 50_000_000,
        "creditScore": 720,
        "hasGuarantor": False,
    }
    payload.update(overrides)
    return payload


def test_health_check(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "UP"}


def test_create_loan_returns_submitted_status(client):
    resp = client.post("/api/v1/loans", json=personal_payload())
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "SUBMITTED"
    assert body["currentStage"] == "VALIDATION"
    assert body["loanId"].startswith("L-")


def test_create_loan_with_malformed_body_returns_400(client):
    resp = client.post("/api/v1/loans", json={"customerId": "C-1"})
    assert resp.status_code == 400
    assert resp.json() == {"error": "INVALID_REQUEST"}


def test_full_happy_path_approves_personal_loan(client):
    create_resp = client.post("/api/v1/loans", json=personal_payload())
    loan_id = create_resp.json()["loanId"]

    process_resp = client.post(f"/api/v1/loans/{loan_id}/process")
    assert process_resp.status_code == 200
    body = process_resp.json()
    assert body["status"] == "APPROVED"
    assert body["currentStage"] is None

    detail = client.get(f"/api/v1/loans/{loan_id}").json()
    assert detail["status"] == "APPROVED"

    history = client.get(f"/api/v1/loans/{loan_id}/history").json()
    stages = [h["stage"] for h in history]
    assert stages == ["VALIDATION", "CHECK_FRAUD", "CHECK_CREDIT"]
    assert all(h["result"] == "PASS" for h in history)


def test_invalid_amount_is_rejected_only_during_processing_not_creation(client):
    create_resp = client.post("/api/v1/loans", json=personal_payload(amount=-5))
    assert create_resp.status_code == 201  # structural validation only

    loan_id = create_resp.json()["loanId"]
    process_resp = client.post(f"/api/v1/loans/{loan_id}/process")
    body = process_resp.json()
    assert body["status"] == "REJECTED"

    history = client.get(f"/api/v1/loans/{loan_id}/history").json()
    assert history[0]["stage"] == "VALIDATION"
    assert history[0]["result"] == "FAIL"
    assert history[0]["reason"] == "INVALID_AMOUNT"


def test_reprocessing_an_approved_loan_does_not_duplicate_history(client):
    create_resp = client.post("/api/v1/loans", json=personal_payload())
    loan_id = create_resp.json()["loanId"]

    client.post(f"/api/v1/loans/{loan_id}/process")
    first_history = client.get(f"/api/v1/loans/{loan_id}/history").json()

    second_process = client.post(f"/api/v1/loans/{loan_id}/process")
    assert second_process.json()["status"] == "APPROVED"

    second_history = client.get(f"/api/v1/loans/{loan_id}/history").json()
    assert second_history == first_history


def test_get_unknown_loan_returns_404(client):
    resp = client.get("/api/v1/loans/L-DOESNOTEXIST")
    assert resp.status_code == 404
    assert resp.json() == {"error": "LOAN_NOT_FOUND"}


def test_process_unknown_loan_returns_404(client):
    resp = client.post("/api/v1/loans/L-DOESNOTEXIST/process")
    assert resp.status_code == 404
    assert resp.json() == {"error": "LOAN_NOT_FOUND"}


def test_business_loan_without_guarantor_is_rejected_end_to_end(client):
    payload = personal_payload(loanType="BUSINESS", hasGuarantor=False)
    create_resp = client.post("/api/v1/loans", json=payload)
    loan_id = create_resp.json()["loanId"]

    process_resp = client.post(f"/api/v1/loans/{loan_id}/process")
    assert process_resp.json()["status"] == "REJECTED"

    history = client.get(f"/api/v1/loans/{loan_id}/history").json()
    assert history[-1]["stage"] == "CHECK_GUARANTOR"
    assert history[-1]["result"] == "FAIL"


def test_manual_review_customer_halts_processing(client):
    payload = personal_payload(customerId="REVIEW-1001")
    create_resp = client.post("/api/v1/loans", json=payload)
    loan_id = create_resp.json()["loanId"]

    process_resp = client.post(f"/api/v1/loans/{loan_id}/process")
    assert process_resp.json()["status"] == "MANUAL_REVIEW"

    # Reprocessing must not change the outcome or add history.
    again = client.post(f"/api/v1/loans/{loan_id}/process")
    assert again.json()["status"] == "MANUAL_REVIEW"
    history = client.get(f"/api/v1/loans/{loan_id}/history").json()
    assert len(history) == 2  # VALIDATION + CHECK_FRAUD only
