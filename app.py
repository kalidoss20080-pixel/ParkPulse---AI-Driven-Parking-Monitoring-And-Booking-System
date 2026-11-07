from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
import sqlite3
from pathlib import Path

app = Flask(__name__)
app.secret_key = "change-this-secret-key"
DB_PATH = Path(__file__).with_name("parking.db")

# The three prototype slots and their approximate distance from the entrance.
DEFAULT_SLOTS = [
    ("A1", 1, "Available"),
    ("A2", 2, "Available"),
    ("A3", 3, "Available"),
]

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS slots (
                slot_id TEXT PRIMARY KEY,
                distance_order INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'Available'
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS bookings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                slot_id TEXT NOT NULL,
                vehicle_number TEXT NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'Booked',
                FOREIGN KEY(slot_id) REFERENCES slots(slot_id)
            )
        """)
        for slot in DEFAULT_SLOTS:
            conn.execute(
                "INSERT OR IGNORE INTO slots(slot_id, distance_order, status) VALUES (?, ?, ?)",
                slot
            )

def expire_old_bookings():
    now = datetime.now()
    with get_db() as conn:
        expired = conn.execute("""
            SELECT slot_id FROM bookings
            WHERE status = 'Booked' AND expires_at <= ?
        """, (now.isoformat(timespec="seconds"),)).fetchall()
        for row in expired:
            conn.execute("""
                UPDATE bookings SET status = 'Expired'
                WHERE slot_id = ? AND status = 'Booked'
            """, (row["slot_id"],))
            conn.execute("""
                UPDATE slots SET status = 'Available'
                WHERE slot_id = ? AND status = 'Reserved'
            """, (row["slot_id"],))

def slot_data():
    expire_old_bookings()
    with get_db() as conn:
        return conn.execute("""
            SELECT s.slot_id, s.distance_order, s.status,
                   b.vehicle_number, b.expires_at
            FROM slots s
            LEFT JOIN bookings b
              ON b.slot_id = s.slot_id AND b.status = 'Booked'
            ORDER BY s.distance_order
        """).fetchall()

@app.route("/")
def index():
    slots = slot_data()
    total = len(slots)
    available = sum(1 for s in slots if s["status"] == "Available")
    nearest = next((s["slot_id"] for s in slots if s["status"] == "Available"), None)
    return render_template(
        "index.html", slots=slots, total=total, available=available,
        percentage=round((available / total) * 100) if total else 0,
        nearest=nearest
    )

@app.route("/book", methods=["POST"])
def book():
    slot_id = request.form.get("slot_id", "").strip().upper()
    vehicle_number = request.form.get("vehicle_number", "").strip().upper()

    if not vehicle_number:
        flash("Enter your vehicle number to continue.", "error")
        return redirect(url_for("index"))

    with get_db() as conn:
        slot = conn.execute("SELECT status FROM slots WHERE slot_id = ?", (slot_id,)).fetchone()
        if not slot or slot["status"] != "Available":
            flash("That slot is no longer available. Please choose another.", "error")
            return redirect(url_for("index"))

        now = datetime.now()
        expiry = now + timedelta(minutes=10)
        conn.execute("""
            INSERT INTO bookings(slot_id, vehicle_number, created_at, expires_at, status)
            VALUES (?, ?, ?, ?, 'Booked')
        """, (slot_id, vehicle_number, now.isoformat(timespec="seconds"),
              expiry.isoformat(timespec="seconds")))
        conn.execute("UPDATE slots SET status = 'Reserved' WHERE slot_id = ?", (slot_id,))

    flash(f"Slot {slot_id} booked. This demo reservation expires in 10 minutes.", "success")
    return redirect(url_for("index"))

@app.route("/operator")
def operator():
    return render_template("operator.html", slots=slot_data())

@app.route("/operator/update", methods=["POST"])
def update_slot():
    slot_id = request.form.get("slot_id", "").strip().upper()
    status = request.form.get("status", "")
    if status not in ("Available", "Occupied"):
        flash("Invalid slot status.", "error")
        return redirect(url_for("operator"))

    with get_db() as conn:
        conn.execute("UPDATE slots SET status = ? WHERE slot_id = ?", (status, slot_id))
        if status == "Occupied":
            conn.execute("""
                UPDATE bookings SET status = 'Arrived'
                WHERE slot_id = ? AND status = 'Booked'
            """, (slot_id,))
        else:
            conn.execute("""
                UPDATE bookings SET status = 'Completed'
                WHERE slot_id = ? AND status IN ('Booked', 'Arrived')
            """, (slot_id,))
    flash(f"Slot {slot_id} updated to {status}.", "success")
    return redirect(url_for("operator"))

@app.route("/api/slots")
def api_slots():
    return jsonify([
        {"slot_id": s["slot_id"], "status": s["status"],
         "distance_order": s["distance_order"]}
        for s in slot_data()
    ])

if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000, debug=True)
