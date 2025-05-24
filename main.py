from fastapi import FastAPI, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import psycopg2
import bcrypt

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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

class GroupMemberRequest(BaseModel):
    group_id: int
    user_id: int
    role: str  # 'driver' or 'collector'

class DriverLocationRequest(BaseModel):
    email: str
    latitude: float
    longitude: float

class TruckRequest(BaseModel):
    plate_number: str
    model: str
    status: str

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
    cur.execute("""
        INSERT INTO driver_locations (user_id, latitude, longitude)
        VALUES (%s, %s, %s)
        ON CONFLICT (user_id) DO UPDATE
        SET latitude = EXCLUDED.latitude, longitude = EXCLUDED.longitude
    """, (user_id, req.latitude, req.longitude))
    conn.commit()
    conn.close()
    return {"success": True, "message": "Location updated"}

@app.get("/driver_locations")
def get_driver_locations():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT u.name, u.email, dl.latitude, dl.longitude
        FROM driver_locations dl
        JOIN users u ON dl.user_id = u.id
    """)
    rows = cur.fetchall()
    conn.close()
    return [
        {
            "name": r[0],
            "email": r[1],
            "latitude": r[2],
            "longitude": r[3],
        }
        for r in rows
    ]

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

@app.get("/reports")
def get_reports():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT gr.id, gr.location, gr.description, u.email, gr.original_level, gr.reported_level
        FROM garbage_reports gr
        JOIN users u ON gr.reporter_id = u.id
        ORDER BY gr.id DESC
    """)
    rows = cur.fetchall()
    conn.close()
    return [
        {
            "id": r[0],
            "location": r[1],
            "description": r[2],
            "email": r[3],
            "original_level": r[4],
            "reported_level": r[5],
        }
        for r in rows
    ]

@app.delete("/reports/{report_id}")
def delete_report(report_id: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM garbage_reports WHERE id = %s", (report_id,))
    conn.commit()
    conn.close()
    return {"success": True}

@app.patch("/reports/{report_id}")
def update_report(report_id: int, data: dict = Body(...)):
    conn = get_conn()
    cur = conn.cursor()
    fields = []
    values = []
    for key in ['description', 'reported_level']:
        if key in data:
            fields.append(f"{key} = %s")
            values.append(data[key])
    if not fields:
        conn.close()
        raise HTTPException(status_code=400, detail="No fields to update")
    values.append(report_id)
    cur.execute(f"UPDATE garbage_reports SET {', '.join(fields)} WHERE id = %s", tuple(values))
    conn.commit()
    conn.close()
    return {"success": True}

@app.get("/groups")
def get_groups():
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT g.id, g.name, g.status, g.area, t.plate_number
            FROM collection_groups g
            LEFT JOIN trucks t ON g.truck_id = t.id
            ORDER BY g.id
        """)
        groups = cur.fetchall()
        group_ids = [g[0] for g in groups]
        if not group_ids:
            return []
        cur.execute("""
            SELECT gm.group_id, u.name, gm.role
            FROM group_members gm
            JOIN users u ON gm.user_id = u.id
            WHERE gm.group_id = ANY(%s)
        """, (group_ids,))
        members = cur.fetchall()
        group_members_map = {}
        for gid, uname, role in members:
            group_members_map.setdefault(gid, []).append({'name': uname, 'role': role})
        return [
            {
                "id": g[0],
                "name": g[1],
                "status": g[2],
                "area": g[3],
                "truck": g[4],
                "members": group_members_map.get(g[0], [])
            }
            for g in groups
        ]
    except Exception as e:
        print("Error in get_groups:", e)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@app.post("/groups")
def create_group(req: GroupRequest):
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO collection_groups (name, status, area, truck_id) VALUES (%s, %s, %s, %s) RETURNING id",
            (req.name, req.status, req.area, req.truck_id)
        )
        group_id = cur.fetchone()[0]
        conn.commit()
        return {"success": True, "group_id": group_id}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        conn.close()

@app.delete("/groups/{group_id}")
def delete_group(group_id: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM collection_groups WHERE id = %s", (group_id,))
    conn.commit()
    conn.close()
    return {"success": True}

@app.patch("/groups/{group_id}")
def update_group(group_id: int, data: dict = Body(...)):
    conn = get_conn()
    cur = conn.cursor()
    fields = []
    values = []
    for key in ['name', 'status', 'area']:
        if key in data:
            fields.append(f"{key} = %s")
            values.append(data[key])
    if not fields:
        conn.close()
        raise HTTPException(status_code=400, detail="No fields to update")
    values.append(group_id)
    cur.execute(f"UPDATE collection_groups SET {', '.join(fields)} WHERE id = %s", tuple(values))
    conn.commit()
    conn.close()
    return {"success": True}

@app.post("/group_members")
def add_group_member(req: GroupMemberRequest):
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO group_members (group_id, user_id, role) VALUES (%s, %s, %s)",
            (req.group_id, req.user_id, req.role)
        )
        conn.commit()
        return {"success": True}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        conn.close()

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

@app.post("/trucks")
def add_truck(req: TruckRequest):
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO trucks (plate_number, model, status) VALUES (%s, %s, %s) RETURNING id",
            (req.plate_number, req.model, req.status)
        )
        truck_id = cur.fetchone()[0]
        conn.commit()
        return {"success": True, "truck_id": truck_id}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        conn.close()

@app.delete("/trucks/{truck_id}")
def delete_truck(truck_id: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM trucks WHERE id = %s", (truck_id,))
    conn.commit()
    conn.close()
    return {"success": True}

@app.patch("/trucks/{truck_id}")
def update_truck(truck_id: int, data: dict = Body(...)):
    conn = get_conn()
    cur = conn.cursor()
    fields = []
    values = []
    for key in ['model', 'status']:
        if key in data:
            fields.append(f"{key} = %s")
            values.append(data[key])
    if not fields:
        conn.close()
        raise HTTPException(status_code=400, detail="No fields to update")
    values.append(truck_id)
    cur.execute(f"UPDATE trucks SET {', '.join(fields)} WHERE id = %s", tuple(values))
    conn.commit()
    conn.close()
    return {"success": True}

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

@app.delete("/users/{user_id}")
def delete_user(user_id: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM users WHERE id = %s", (user_id,))
    conn.commit()
    conn.close()
    return {"success": True}

@app.patch("/users/{user_id}")
def update_user(user_id: int, data: dict = Body(...)):
    conn = get_conn()
    cur = conn.cursor()
    fields = []
    values = []
    for key in ['name', 'contact']:
        if key in data:
            fields.append(f"{'contact_number' if key == 'contact' else key} = %s")
            values.append(data[key])
    if not fields:
        conn.close()
        raise HTTPException(status_code=400, detail="No fields to update")
    values.append(user_id)
    cur.execute(f"UPDATE users SET {', '.join(fields)} WHERE id = %s", tuple(values))
    conn.commit()
    conn.close()
    return {"success": True}
