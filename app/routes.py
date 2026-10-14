import csv
import io
from datetime import datetime, date
from flask import Blueprint, render_template, request, redirect, url_for, flash, Response, current_app
from app.db import get_connection

bp = Blueprint("main", __name__)

def get_db():
    return get_connection(current_app.config["DATABASE"])

@bp.route("/")
def dashboard():
    conn = get_db()
    today_str = date.today().isoformat()
    
    # Stats summary for today
    total_members = conn.execute("SELECT COUNT(*) FROM members WHERE is_active = 1").fetchone()[0]
    status_counts = {"Present": 0, "Late": 0, "Absent": 0, "Excused": 0}
    
    rows = conn.execute("""
        SELECT status, COUNT(*) as count 
        FROM attendance 
        WHERE date = ? 
        GROUP BY status
    """, (today_str,)).fetchall()
    for r in rows:
        status_counts[r["status"]] = r["count"]
        
    recorded = sum(status_counts.values())
    unmarked = max(0, total_members - recorded)
    attendance_rate = round(((status_counts["Present"] + status_counts["Late"]) / total_members * 100), 1) if total_members else 0
    
    # Recent activity logs
    recent_logs = conn.execute("""
        SELECT a.*, m.name, m.code, m.department
        FROM attendance a
        JOIN members m ON a.member_id = m.id
        ORDER BY a.id DESC LIMIT 10
    """).fetchall()
    
    members = conn.execute("SELECT id, code, name FROM members WHERE is_active = 1 ORDER BY name ASC").fetchall()
    conn.close()
    
    return render_template(
        "dashboard.html",
        today=today_str,
        total_members=total_members,
        status_counts=status_counts,
        unmarked=unmarked,
        attendance_rate=attendance_rate,
        recent_logs=recent_logs,
        members=members
    )

@bp.route("/punch", methods=["POST"])
def quick_punch():
    code = request.form.get("badge_code", "").strip().upper()
    action = request.form.get("action", "in") # 'in' or 'out'
    today_str = date.today().isoformat()
    now_time = datetime.now().strftime("%H:%M:%S")
    
    if not code:
        flash("Please enter or scan a Member Badge ID.", "error")
        return redirect(url_for("main.dashboard"))
        
    conn = get_db()
    member = conn.execute("SELECT * FROM members WHERE code = ? AND is_active = 1", (code,)).fetchone()
    if not member:
        conn.close()
        flash(f"No active member found with ID: {code}", "error")
        return redirect(url_for("main.dashboard"))
        
    record = conn.execute("SELECT * FROM attendance WHERE member_id = ? AND date = ?", (member["id"], today_str)).fetchone()
    
    if action == "in":
        if record and record["check_in"]:
            flash(f"{member['name']} has already checked in today at {record['check_in']}.", "warning")
        else:
            # Determine if late (e.g., after 09:15:00)
            status = "Late" if now_time > "09:15:00" else "Present"
            if record:
                conn.execute("UPDATE attendance SET check_in = ?, status = ? WHERE id = ?", (now_time, status, record["id"]))
            else:
                conn.execute("""
                    INSERT INTO attendance (member_id, date, check_in, status, note)
                    VALUES (?, ?, ?, ?, ?)
                """, (member["id"], today_str, now_time, status, "Quick Punch-in"))
            conn.commit()
            flash(f"Checked IN: {member['name']} at {now_time} ({status})", "success")
    else: # check-out
        if not record:
            conn.execute("""
                INSERT INTO attendance (member_id, date, check_out, status, note)
                VALUES (?, ?, ?, 'Present', 'Auto Check-out')
            """, (member["id"], today_str, now_time))
            conn.commit()
            flash(f"Checked OUT: {member['name']} at {now_time}", "info")
        else:
            conn.execute("UPDATE attendance SET check_out = ? WHERE id = ?", (now_time, record["id"]))
            conn.commit()
            flash(f"Checked OUT: {member['name']} at {now_time}", "info")
            
    conn.close()
    return redirect(url_for("main.dashboard"))

@bp.route("/members", methods=["GET", "POST"])
def members():
    conn = get_db()
    if request.method == "POST":
        code = request.form.get("code", "").strip().upper()
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        department = request.form.get("department", "General").strip()
        role = request.form.get("role", "Member").strip()
        
        if not code or not name or not email:
            flash("Badge Code, Name, and Email are required!", "error")
        else:
            try:
                conn.execute("""
                    INSERT INTO members (code, name, email, department, role, is_active, created_at)
                    VALUES (?, ?, ?, ?, ?, 1, ?)
                """, (code, name, email, department, role, datetime.now().isoformat()))
                conn.commit()
                flash(f"Member '{name}' ({code}) registered successfully!", "success")
            except Exception as e:
                flash(f"Error adding member: {e}", "error")
        return redirect(url_for("main.members"))
        
    search = request.args.get("q", "").strip()
    query = "SELECT * FROM members"
    params = []
    if search:
        query += " WHERE name LIKE ? OR code LIKE ? OR department LIKE ?"
        params.extend([f"%{search}%", f"%{search}%", f"%{search}%"])
    query += " ORDER BY name ASC"
    
    members_list = conn.execute(query, params).fetchall()
    conn.close()
    return render_template("members.html", members=members_list, search=search)

@bp.route("/members/toggle/<int:member_id>", methods=["POST"])
def toggle_member(member_id):
    conn = get_db()
    member = conn.execute("SELECT is_active, name FROM members WHERE id = ?", (member_id,)).fetchone()
    if member:
        new_status = 0 if member["is_active"] == 1 else 1
        conn.execute("UPDATE members SET is_active = ? WHERE id = ?", (new_status, member_id))
        conn.commit()
        state = "activated" if new_status == 1 else "deactivated"
        flash(f"Member {member['name']} {state}.", "info")
    conn.close()
    return redirect(url_for("main.members"))

@bp.route("/attendance", methods=["GET", "POST"])
def attendance():
    conn = get_db()
    selected_date = request.args.get("date", date.today().isoformat())
    selected_dept = request.args.get("department", "All")
    
    if request.method == "POST":
        target_date = request.form.get("target_date", selected_date)
        status_map = {}
        for key, value in request.form.items():
            if key.startswith("status_"):
                member_id = int(key.split("_")[1])
                status_map[member_id] = value
                
        for member_id, status in status_map.items():
            note = request.form.get(f"note_{member_id}", "")
            conn.execute("""
                INSERT INTO attendance (member_id, date, status, note)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(member_id, date) DO UPDATE SET
                status = excluded.status,
                note = excluded.note
            """, (member_id, target_date, status, note))
        conn.commit()
        flash(f"Attendance updated for {target_date}.", "success")
        conn.close()
        return redirect(url_for("main.attendance", date=target_date, department=selected_dept))

    # Get unique departments
    depts = [row[0] for row in conn.execute("SELECT DISTINCT department FROM members ORDER BY department").fetchall()]
    
    # Fetch members with attendance status for the selected date
    query = """
        SELECT m.id, m.code, m.name, m.department, a.status, a.check_in, a.check_out, a.note
        FROM members m
        LEFT JOIN attendance a ON m.id = a.member_id AND a.date = ?
        WHERE m.is_active = 1
    """
    params = [selected_date]
    if selected_dept != "All":
        query += " AND m.department = ?"
        params.append(selected_dept)
    query += " ORDER BY m.name ASC"
    
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return render_template("attendance.html", rows=rows, selected_date=selected_date, departments=depts, selected_dept=selected_dept)

@bp.route("/reports")
def reports():
    conn = get_db()
    from_date = request.args.get("from_date", date.today().replace(day=1).isoformat())
    to_date = request.args.get("to_date", date.today().isoformat())
    dept = request.args.get("department", "All")
    
    query = """
        SELECT a.date, a.check_in, a.check_out, a.status, a.note,
               m.code, m.name, m.department
        FROM attendance a
        JOIN members m ON a.member_id = m.id
        WHERE a.date BETWEEN ? AND ?
    """
    params = [from_date, to_date]
    if dept != "All":
        query += " AND m.department = ?"
        params.append(dept)
    query += " ORDER BY a.date DESC, m.name ASC"
    
    logs = conn.execute(query, params).fetchall()
    depts = [row[0] for row in conn.execute("SELECT DISTINCT department FROM members ORDER BY department").fetchall()]
    
    # Calculate member stats aggregate
    member_stats = conn.execute("""
        SELECT m.name, m.code, m.department,
               COUNT(a.id) as total_days,
               SUM(CASE WHEN a.status = 'Present' THEN 1 ELSE 0 END) as present_count,
               SUM(CASE WHEN a.status = 'Late' THEN 1 ELSE 0 END) as late_count,
               SUM(CASE WHEN a.status = 'Absent' THEN 1 ELSE 0 END) as absent_count
        FROM members m
        LEFT JOIN attendance a ON m.id = a.member_id AND a.date BETWEEN ? AND ?
        WHERE m.is_active = 1
        GROUP BY m.id
        ORDER BY m.name ASC
    """, (from_date, to_date)).fetchall()
    
    conn.close()
    return render_template("reports.html", logs=logs, member_stats=member_stats, from_date=from_date, to_date=to_date, departments=depts, selected_dept=dept)

@bp.route("/reports/export")
def export_csv():
    from_date = request.args.get("from_date", date.today().replace(day=1).isoformat())
    to_date = request.args.get("to_date", date.today().isoformat())
    dept = request.args.get("department", "All")
    
    conn = get_db()
    query = """
        SELECT a.date, m.code, m.name, m.department, a.status, a.check_in, a.check_out, a.note
        FROM attendance a
        JOIN members m ON a.member_id = m.id
        WHERE a.date BETWEEN ? AND ?
    """
    params = [from_date, to_date]
    if dept != "All":
        query += " AND m.department = ?"
        params.append(dept)
    query += " ORDER BY a.date DESC, m.name ASC"
    
    rows = conn.execute(query, params).fetchall()
    conn.close()
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Date", "Badge ID", "Name", "Department", "Status", "Check In", "Check Out", "Notes"])
    
    for r in rows:
        writer.writerow([r["date"], r["code"], r["name"], r["department"], r["status"], r["check_in"] or "-", r["check_out"] or "-", r["note"] or ""])
        
    response = Response(output.getvalue(), mimetype="text/csv")
    response.headers["Content-Disposition"] = f"attachment; filename=attendance_report_{from_date}_{to_date}.csv"
    return response
