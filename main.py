from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import psycopg2
import bcrypt

app = FastAPI()

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
    original_level: str = None
    reported_level: str = None

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
    # Find user id by email
    cur.execute("SELECT id FROM users WHERE email = %s", (req.email,))
    user = cur.fetchone()
    if not user:
        conn.close()
        raise HTTPException(status_code=404, detail="User not found")
    user_id = user[0]
    # Insert report with original_level and reported_level
    cur.execute(
        "INSERT INTO garbage_reports (location, description, reporter_id, original_level, reported_level) VALUES (%s, %s, %s, %s, %s)",
        (req.location, req.description, user_id, req.original_level, req.reported_level)
    )
    conn.commit()
    conn.close()
    return {"success": True, "message": "Report submitted"}
