from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import psycopg2
import bcrypt

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For production, restrict to your web app's URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB = {
    "host": "dpg-d0mr31m3jp1c738jr810-a",
    "port": 5432,
    "user": "gtrash_user",
    "password": "eRamXO4QuE5SXVhcQsEX62xIIaHEHZWZ",
    "dbname": "gtrash"
}

def get_conn():
    return psycopg2.connect(
        host=DB["host"],
        port=DB["port"],
        user=DB["user"],
        password=DB["password"],
        dbname=DB["dbname"]
    )

class RegisterRequest(BaseModel):
    email: str
    password: str
    name: str
    contact: str
    role: str

class LoginRequest(BaseModel):
    email: str
    password: str

class ReportRequest(BaseModel):
    location: str
    description: str
    email: str
    original_level: Optional[str] = None
    reported_level: Optional[str] = None

class GroupRequest(BaseModel):
    name: str
    status: str  # e.g. 'idle', 'on_road', 'collecting'
    area: str
    truck_id: Optional[int] = None
    personnel_id: Optional[int] = None

# --- DRIVER LOCATION ENDPOINT ---
class DriverLocationRequest(BaseModel):
    email: str
    latitude: float
    longitude: float

@app.post("/driver_location")
def driver_location(req: DriverLocationRequest):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id FROM users WHERE email = %s", (req.email,))
    user = cur.fetchone()
    if not user:
        conn.close()
        raise HTTPException(status_code=404, detail="User not found")
    user_id = user[0]
    # Insert or update the driver's location
    cur.execute("""
        INSERT INTO driver_locations (user_id, latitude, longitude)
        VALUES (%s, %s, %s)
        ON CONFLICT (user_id) DO UPDATE
        SET latitude = EXCLUDED.latitude, longitude = EXCLUDED.longitude
    """, (user_id, req.latitude, req.longitude))
    conn.commit()
    conn.close()
    return {"success": True, "message": "Location updated"}

@app.post("/register")
def register(req: RegisterRequest):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT email FROM users WHERE email = %s", (req.email,))
    if cur.fetchone():
        conn.close()
        raise HTTPException(status_code=400, detail="Email already registered.")
    hashed = bcrypt.hashpw(req.password.encode(), bcrypt.gensalt()).decode()
    cur.execute(
        "INSERT INTO users (email, password, role, name, contact_number) VALUES (%s, %s, %s, %s, %s)",
        (req.email, hashed, req.role, req.name, req.contact)
    )
    conn.commit()
    conn.close()
    return {"success": True}

@app.post("/login")
def login(req: LoginRequest):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT password, role FROM users WHERE email = %s", (req.email,))
    row = cur.fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=400, detail="Email not found.")
    hashed, role = row
    if not bcrypt.checkpw(req.password.encode(), hashed.encode()):
        raise HTTPException(status_code=400, detail="Incorrect password.")
    return {"success": True, "role": role}

@app.post("/report")
def create_report(req: ReportRequest):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id FROM users WHERE email = %s", (req.email,))
    user = cur.fetchone()
    if not user:
        conn.close()
        raise HTTPException(status_code=404, detail="User not found")
    user_id = user[0]
    cur.execute(
        "INSERT INTO garbage_reports (location, description, reporter_id, original_level, reported_level) VALUES (%s, %s, %s, %s, %s)",
        (req.location, req.description, user_id, req.original_level, req.reported_level)
    )
    conn.commit()
    conn.close()
    return {"success": True, "message": "Report submitted"}

# --- LGU Dashboard Endpoints ---

@app.get("/reports")
def get_reports():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT gr.location, gr.description, u.email, gr.original_level, gr.reported_level
        FROM garbage_reports gr
        JOIN users u ON gr.reporter_id = u.id
        ORDER BY gr.id DESC
    """)
    rows = cur.fetchall()
    conn.close()
    return [
        {
            "location": r[0],
            "description": r[1],
            "email": r[2],
            "original_level": r[3],
            "reported_level": r[4],
        }
        for r in rows
    ]

@app.get("/groups")
def get_groups():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT g.name, g.status, g.area, t.plate_number, p.name
        FROM collection_groups g
        LEFT JOIN trucks t ON g.truck_id = t.id
        LEFT JOIN personnel p ON g.personnel_id = p.id
        ORDER BY g.id
    """)
    rows = cur.fetchall()
    conn.close()
    return [
        {
            "name": r[0],
            "status": r[1],  # idle, on_road, collecting
            "area": r[2],
            "truck": r[3],
            "personnel": r[4],
        }
        for r in rows
    ]

@app.post("/groups")
def create_group(req: GroupRequest):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO collection_groups (name, status, area, truck_id, personnel_id) VALUES (%s, %s, %s, %s, %s) RETURNING id",
        (req.name, req.status, req.area, req.truck_id, req.personnel_id)
    )
    group_id = cur.fetchone()[0]
    conn.commit()
    conn.close()
    return {"success": True, "group_id": group_id}

@app.get("/trucks")
def get_trucks():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id, plate_number, model, status FROM trucks ORDER BY id")
    rows = cur.fetchall()
    conn.close()
    return [
        {
            "id": r[0],
            "plate_number": r[1],
            "model": r[2],
            "status": r[3],
        }
        for r in rows
    ]

@app.get("/personnel")
def get_personnel():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id, name, role, contact_number FROM personnel ORDER BY id")
    rows = cur.fetchall()
    conn.close()
    return [
        {
            "id": r[0],
            "name": r[1],
            "role": r[2],
            "contact": r[3],
        }
        for r in rows
    ]

@app.get("/users")
def get_users():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id, email, name, role, contact_number FROM users ORDER BY id")
    rows = cur.fetchall()
    conn.close()
    return [
        {
            "id": r[0],
            "email": r[1],
            "name": r[2],
            "role": r[3],
            "contact": r[4],
        }
        for r in rows
    ]
