import os
import tempfile
import pytest
from app import create_app
from app.db import get_connection
from datetime import date

@pytest.fixture
def app():
    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    app = create_app({
        "TESTING": True,
        "DATABASE": db_path,
        "SECRET_KEY": "test-secret"
    })
    yield app
    
    os.close(db_fd)
    if os.path.exists(db_path):
        os.unlink(db_path)

@pytest.fixture
def client(app):
    return app.test_client()

def test_dashboard_renders(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"Attendance Dashboard" in response.data
    assert b"EMP001" in response.data

def test_quick_punch_check_in(client, app):
    today = date.today().isoformat()
    # Punch in for Alice (EMP001)
    res = client.post("/punch", data={"badge_code": "EMP001", "action": "in"}, follow_redirects=True)
    assert res.status_code == 200
    assert b"Checked IN: Alice Smith" in res.data
    
    # Verify in DB
    with app.app_context():
        conn = get_connection(app.config["DATABASE"])
        row = conn.execute("SELECT * FROM attendance WHERE date = ?", (today,)).fetchone()
        assert row is not None
        assert row["status"] in ("Present", "Late")
        assert row["check_in"] is not None
        conn.close()

def test_quick_punch_check_out(client, app):
    # First punch in
    client.post("/punch", data={"badge_code": "EMP002", "action": "in"})
    # Now punch out
    res = client.post("/punch", data={"badge_code": "EMP002", "action": "out"}, follow_redirects=True)
    assert res.status_code == 200
    assert b"Checked OUT: Bob Jones" in res.data

def test_quick_punch_invalid_code(client):
    res = client.post("/punch", data={"badge_code": "NONEXISTENT", "action": "in"}, follow_redirects=True)
    assert res.status_code == 200
    assert b"No active member found with ID: NONEXISTENT" in res.data

def test_add_and_toggle_member(client, app):
    # Add a member
    res = client.post("/members", data={
        "code": "NEW999",
        "name": "Testing User",
        "email": "testuser@example.com",
        "department": "QA",
        "role": "QA Lead"
    }, follow_redirects=True)
    assert res.status_code == 200
    assert b"Testing User" in res.data
    
    # Toggle status
    with app.app_context():
        conn = get_connection(app.config["DATABASE"])
        member = conn.execute("SELECT id, is_active FROM members WHERE code = 'NEW999'").fetchone()
        assert member["is_active"] == 1
        member_id = member["id"]
        conn.close()
        
    toggle_res = client.post(f"/members/toggle/{member_id}", follow_redirects=True)
    assert toggle_res.status_code == 200
    assert b"deactivated" in toggle_res.data

def test_batch_mark_attendance(client, app):
    today = date.today().isoformat()
    with app.app_context():
        conn = get_connection(app.config["DATABASE"])
        m = conn.execute("SELECT id FROM members LIMIT 1").fetchone()
        mid = m["id"]
        conn.close()
        
    res = client.post("/attendance", data={
        "target_date": today,
        f"status_{mid}": "Excused",
        f"note_{mid}": "Doctor visit"
    }, follow_redirects=True)
    assert res.status_code == 200
    
    with app.app_context():
        conn = get_connection(app.config["DATABASE"])
        record = conn.execute("SELECT * FROM attendance WHERE member_id = ? AND date = ?", (mid, today)).fetchone()
        assert record["status"] == "Excused"
        assert record["note"] == "Doctor visit"
        conn.close()

def test_export_csv(client):
    today = date.today().isoformat()
    # Trigger at least one record
    client.post("/punch", data={"badge_code": "EMP001", "action": "in"})
    
    res = client.get(f"/reports/export?from_date={today}&to_date={today}&department=All")
    assert res.status_code == 200
    assert res.mimetype == "text/csv"
    assert b"Badge ID,Name,Department,Status" in res.data
    assert b"Alice Smith" in res.data
