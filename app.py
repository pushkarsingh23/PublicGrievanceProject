
from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
import uuid
import os
from datetime import datetime
from functools import wraps

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-secret-key")

DATABASE = "complaints.db"
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")


# Database connection
def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


# Create database table
def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS complaints (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tracking_id TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            email TEXT,
            complaint TEXT NOT NULL,
            category TEXT NOT NULL,
            status TEXT DEFAULT 'Pending',
            created_at TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()


# Complaint category detection
def categorize_complaint(complaint):
    text = complaint.lower()

    categories = {
        "Sanitation": ["garbage", "dustbin", "waste", "dirty", "cleaning"],
        "Roads": ["road", "pothole", "street", "traffic"],
        "Water": ["water", "pipeline", "leakage", "supply"],
        "Electricity": ["electricity", "power", "electric", "lights"],
        "Healthcare": ["hospital", "doctor", "medicine", "health"],
        "Education": ["school", "college", "teacher", "education"]
    }

    for category, keywords in categories.items():
        if any(word in text for word in keywords):
            return category

    return "Other / Unclassified"


# Admin login protection
def admin_required(function):
    @wraps(function)
    def wrapper(*args, **kwargs):
        if not session.get("admin"):
            return redirect(url_for("admin_login"))
        return function(*args, **kwargs)
    return wrapper


# Home page and complaint submission
@app.route("/", methods=["GET", "POST"])
def home():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        complaint = request.form.get("complaint", "").strip()

        if not name or not complaint:
            flash("Please enter your name and complaint.")
            return redirect(url_for("home"))

        category = categorize_complaint(complaint)
        tracking_id = uuid.uuid4().hex[:10].upper()

        conn = get_db()
        conn.execute("""
            INSERT INTO complaints
            (tracking_id, name, email, complaint, category, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            tracking_id, name, email, complaint,
            category, "Pending",
            datetime.now().strftime("%d-%m-%Y %I:%M %p")
        ))
        conn.commit()
        conn.close()

        return render_template(
            "index.html",
            category=category,
            complaint=complaint,
            tracking_id=tracking_id,
            submitted=True
        )

    return render_template("index.html")


# Complaint tracking
@app.route("/track", methods=["GET", "POST"])
def track():
    complaint = None

    if request.method == "POST":
        tracking_id = request.form.get("tracking_id", "").strip().upper()

        conn = get_db()
        complaint = conn.execute(
            "SELECT * FROM complaints WHERE tracking_id = ?",
            (tracking_id,)
        ).fetchone()
        conn.close()

        if complaint is None:
            flash("Complaint not found. Please check your tracking ID.")

    return render_template("track.html", complaint=complaint)


# Admin login
@app.route("/admin", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        password = request.form.get("password", "")

        if password == ADMIN_PASSWORD:
            session["admin"] = True
            return redirect(url_for("dashboard"))

        flash("Incorrect admin password.")

    return render_template("admin_login.html")


# Admin dashboard
@app.route("/dashboard")
@admin_required
def dashboard():
    conn = get_db()

    complaints = conn.execute(
        "SELECT * FROM complaints ORDER BY id DESC"
    ).fetchall()

    total = conn.execute(
        "SELECT COUNT(*) FROM complaints"
    ).fetchone()[0]

    pending = conn.execute(
        "SELECT COUNT(*) FROM complaints WHERE status = 'Pending'"
    ).fetchone()[0]

    in_progress = conn.execute(
        "SELECT COUNT(*) FROM complaints WHERE status = 'In Progress'"
    ).fetchone()[0]

    resolved = conn.execute(
        "SELECT COUNT(*) FROM complaints WHERE status = 'Resolved'"
    ).fetchone()[0]

    conn.close()

    return render_template(
        "dashboard.html",
        complaints=complaints,
        total=total,
        pending=pending,
        in_progress=in_progress,
        resolved=resolved
    )


# Update complaint status
@app.route("/update-status/<int:complaint_id>", methods=["POST"])
@admin_required
def update_status(complaint_id):
    status = request.form.get("status")

    allowed_statuses = ["Pending", "In Progress", "Resolved"]

    if status in allowed_statuses:
        conn = get_db()
        conn.execute(
            "UPDATE complaints SET status = ? WHERE id = ?",
            (status, complaint_id)
        )
        conn.commit()
        conn.close()
        flash("Complaint status updated successfully.")

    return redirect(url_for("dashboard"))


# Admin logout
@app.route("/logout")
@admin_required
def logout():
    session.clear()
    return redirect(url_for("admin_login"))


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
