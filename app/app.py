import os
import sqlite3
from datetime import date, timedelta
from flask import Flask, jsonify, render_template, request, g
from prometheus_client import Counter, Gauge, generate_latest, CONTENT_TYPE_LATEST

app = Flask(__name__)
DB_PATH = os.getenv("DATABASE_PATH", "data/vehicles.db")
REQUESTS = Counter("vehicle_app_requests_total", "HTTP requests handled", ["method", "endpoint"])
VEHICLES = Gauge("vehicle_app_vehicles_total", "Vehicles stored")
REMINDERS_DUE = Gauge("vehicle_app_reminders_due", "Open reminders due within 30 days")

SCHEMA = """
CREATE TABLE IF NOT EXISTS vehicles (
 id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, make TEXT NOT NULL,
 model TEXT NOT NULL, year INTEGER NOT NULL, plate TEXT NOT NULL UNIQUE,
 odometer INTEGER NOT NULL DEFAULT 0, color TEXT NOT NULL DEFAULT '#4c7cff', created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS services (
 id INTEGER PRIMARY KEY AUTOINCREMENT, vehicle_id INTEGER NOT NULL REFERENCES vehicles(id) ON DELETE CASCADE,
 service_type TEXT NOT NULL, service_date TEXT NOT NULL, due_date TEXT NOT NULL,
 due_odometer INTEGER, notes TEXT NOT NULL DEFAULT '', completed INTEGER NOT NULL DEFAULT 0,
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""

def db():
    if "db" not in g:
        os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
        g.db.executescript(SCHEMA)
        if g.db.execute("SELECT COUNT(*) FROM vehicles").fetchone()[0] == 0 and os.getenv("LOAD_DEMO_DATA", "true").lower() == "true":
            seed_demo(g.db)
    return g.db

def seed_demo(conn):
    today = date.today()
    vehicles = [
        ("Daily driver", "Toyota", "RAV4", 2022, "KXY-2481", 28450, "#7799ff"),
        ("Weekend cruiser", "Honda", "Civic", 2020, "JMR-9032", 41280, "#d29b64"),
        ("Family hauler", "Subaru", "Outback", 2023, "NVP-6175", 12720, "#65aa91"),
    ]
    conn.executemany("INSERT INTO vehicles(name,make,model,year,plate,odometer,color) VALUES(?,?,?,?,?,?,?)", vehicles)
    conn.executemany("INSERT INTO services(vehicle_id,service_type,service_date,due_date,due_odometer,notes) VALUES(?,?,?,?,?,?)", [
        (1,"Oil & filter change",(today-timedelta(days=165)).isoformat(),(today+timedelta(days=9)).isoformat(),30000,"Full synthetic oil and OEM filter"),
        (1,"Tire rotation",(today-timedelta(days=120)).isoformat(),(today+timedelta(days=18)).isoformat(),30000,"Rotate and balance all four tires"),
        (2,"Brake inspection",(today-timedelta(days=190)).isoformat(),(today-timedelta(days=2)).isoformat(),None,"Check pads and rotors"),
        (3,"Annual inspection",(today-timedelta(days=300)).isoformat(),(today+timedelta(days=65)).isoformat(),None,"State safety inspection"),
    ])
    conn.commit()

@app.teardown_appcontext
def close_db(_error):
    connection = g.pop("db", None)
    if connection is not None: connection.close()

def record_request():
    REQUESTS.labels(request.method, request.endpoint or "unknown").inc()

def as_dict(row): return dict(row) if row else None

@app.get("/")
def index():
    record_request()
    return render_template("index.html")

@app.get("/api/summary")
def summary():
    record_request(); conn=db()
    total=conn.execute("SELECT COUNT(*) FROM vehicles").fetchone()[0]
    open_count=conn.execute("SELECT COUNT(*) FROM services WHERE completed=0").fetchone()[0]
    due=conn.execute("SELECT COUNT(*) FROM services WHERE completed=0 AND date(due_date)<=date('now','+30 days')").fetchone()[0]
    overdue=conn.execute("SELECT COUNT(*) FROM services WHERE completed=0 AND date(due_date)<date('now')").fetchone()[0]
    VEHICLES.set(total); REMINDERS_DUE.set(due)
    return jsonify({"vehicles":total,"open_reminders":open_count,"due_soon":due,"overdue":overdue})

@app.get("/api/vehicles")
def list_vehicles():
    record_request(); conn=db()
    rows=conn.execute("""SELECT v.*, (SELECT COUNT(*) FROM services s WHERE s.vehicle_id=v.id AND s.completed=0) AS reminder_count,
      (SELECT MIN(due_date) FROM services s WHERE s.vehicle_id=v.id AND s.completed=0) AS next_due
      FROM vehicles v ORDER BY v.created_at DESC, v.id DESC""").fetchall()
    return jsonify([as_dict(r) for r in rows])

@app.post("/api/vehicles")
def create_vehicle():
    record_request(); data=request.get_json(silent=True) or {}
    required=["name","make","model","year","plate"]
    if any(not str(data.get(k," ")).strip() for k in required): return jsonify(error="Please fill in all required vehicle details."),400
    try:
        cur=db().execute("INSERT INTO vehicles(name,make,model,year,plate,odometer,color) VALUES(?,?,?,?,?,?,?)",(data["name"].strip(),data["make"].strip(),data["model"].strip(),int(data["year"]),data["plate"].strip().upper(),int(data.get("odometer") or 0),data.get("color") or "#4c7cff")); db().commit()
        return jsonify(id=cur.lastrowid),201
    except sqlite3.IntegrityError: return jsonify(error="That license plate is already on your list."),409
    except (ValueError,TypeError): return jsonify(error="Year and odometer must be valid numbers."),400

@app.get("/api/services")
def list_services():
    record_request()
    rows=db().execute("""SELECT s.*,v.name AS vehicle_name,v.make,v.model,v.plate,v.color FROM services s JOIN vehicles v ON v.id=s.vehicle_id
      ORDER BY s.completed ASC, s.due_date ASC""").fetchall()
    return jsonify([as_dict(r) for r in rows])

@app.post("/api/services")
def create_service():
    record_request(); data=request.get_json(silent=True) or {}
    if not all(str(data.get(k," ")).strip() for k in ("vehicle_id","service_type","service_date","due_date")): return jsonify(error="Choose a vehicle, service, and both dates."),400
    try:
        cur=db().execute("INSERT INTO services(vehicle_id,service_type,service_date,due_date,due_odometer,notes) VALUES(?,?,?,?,?,?)",(int(data["vehicle_id"]),data["service_type"].strip(),data["service_date"],data["due_date"],int(data["due_odometer"]) if data.get("due_odometer") else None,data.get("notes","").strip())); db().commit()
        return jsonify(id=cur.lastrowid),201
    except (ValueError,TypeError,sqlite3.IntegrityError): return jsonify(error="Could not save reminder. Check the vehicle and mileage."),400

@app.patch("/api/services/<int:service_id>/complete")
def complete_service(service_id):
    record_request(); cur=db().execute("UPDATE services SET completed=1 WHERE id=?",(service_id,)); db().commit()
    if not cur.rowcount: return jsonify(error="Reminder not found."),404
    return jsonify(ok=True)

@app.get("/health")
def health(): return jsonify(status="ok")

@app.get("/metrics")
def metrics(): return generate_latest(), 200, {"Content-Type":CONTENT_TYPE_LATEST}

if __name__ == "__main__": app.run(host="0.0.0.0",port=5000,debug=False)
