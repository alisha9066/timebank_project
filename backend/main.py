from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List
import sqlite3

app = FastAPI(title="Time Bank API")
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # allow all origins (frontend http://127.0.0.1:5500)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_db():
    conn = sqlite3.connect("timebank.db")
    conn.row_factory = sqlite3.Row
    return conn

# Models
class User(BaseModel):
    id: int | None = None
    name: str
    minutes_balance: int = 0

class Service(BaseModel):
    id: int | None = None
    title: str
    description: str | None = None
    provider_user_id: int
    duration_minutes: int = 60

class Transaction(BaseModel):
    id: int | None = None
    provider_user_id: int
    recipient_user_id: int
    minutes: int
    description: str | None = None

# Initialize tables
def init_db():
    conn = get_db()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    minutes_balance INTEGER DEFAULT 0
                )''')
    c.execute('''CREATE TABLE IF NOT EXISTS services (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    description TEXT,
                    provider_user_id INTEGER,
                    duration_minutes INTEGER DEFAULT 60
                )''')
    c.execute('''CREATE TABLE IF NOT EXISTS transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    provider_user_id INTEGER,
                    recipient_user_id INTEGER,
                    minutes INTEGER,
                    description TEXT
                )''')
    conn.commit()
    conn.close()

@app.on_event("startup")
def startup():
    init_db()

# CRUD for Users
@app.post("/users", response_model=User)
def create_user(user: User):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("INSERT INTO users (name, minutes_balance) VALUES (?, ?)", (user.name, user.minutes_balance))
    conn.commit()
    user.id = cur.lastrowid
    conn.close()
    return user

@app.get("/users", response_model=List[User])
def list_users():
    conn = get_db()
    users = conn.execute("SELECT * FROM users").fetchall()
    conn.close()
    return [dict(u) for u in users]

@app.get("/users/{user_id}", response_model=User)
def get_user(user_id: int):
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    conn.close()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return dict(user)

@app.put("/users/{user_id}", response_model=User)
def update_user(user_id: int, user: User):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("UPDATE users SET name=?, minutes_balance=? WHERE id=?", (user.name, user.minutes_balance, user_id))
    conn.commit()
    conn.close()
    user.id = user_id
    return user

@app.delete("/users/{user_id}")
def delete_user(user_id: int):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM users WHERE id=?", (user_id,))
    conn.commit()
    conn.close()
    return {"message": "User deleted"}

# CRUD for Services
@app.post("/services", response_model=Service)
def create_service(service: Service):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("INSERT INTO services (title, description, provider_user_id, duration_minutes) VALUES (?, ?, ?, ?)",
                (service.title, service.description, service.provider_user_id, service.duration_minutes))
    conn.commit()
    service.id = cur.lastrowid
    conn.close()
    return service

@app.get("/services", response_model=List[Service])
def list_services():
    conn = get_db()
    services = conn.execute("SELECT * FROM services").fetchall()
    conn.close()
    return [dict(s) for s in services]

# Transaction logic
@app.post("/transactions", response_model=Transaction)
def create_transaction(tx: Transaction):
    conn = get_db()
    cur = conn.cursor()

    provider = cur.execute("SELECT * FROM users WHERE id=?", (tx.provider_user_id,)).fetchone()
    recipient = cur.execute("SELECT * FROM users WHERE id=?", (tx.recipient_user_id,)).fetchone()
    if not provider or not recipient:
        raise HTTPException(status_code=404, detail="Invalid provider or recipient")

    if recipient["minutes_balance"] < tx.minutes:
        raise HTTPException(status_code=400, detail="Recipient does not have enough minutes to pay")

    # Transfer logic
    cur.execute("UPDATE users SET minutes_balance = minutes_balance + ? WHERE id=?", (tx.minutes, tx.provider_user_id))
    cur.execute("UPDATE users SET minutes_balance = minutes_balance - ? WHERE id=?", (tx.minutes, tx.recipient_user_id))

    cur.execute("INSERT INTO transactions (provider_user_id, recipient_user_id, minutes, description) VALUES (?, ?, ?, ?)",
                (tx.provider_user_id, tx.recipient_user_id, tx.minutes, tx.description))

    conn.commit()
    tx.id = cur.lastrowid
    conn.close()
    return tx
