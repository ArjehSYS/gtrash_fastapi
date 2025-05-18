from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import psycopg2
import bcrypt

app = FastAPI()

DB = {
    "host": "trolley.proxy.rlwy.net",
    "port": 22193,
    "user": "postgres",
    "password": "GOCwYwbbadFCQRsXbDBXOWDIsnvoNUqo",
    "dbname": "railway"
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