# main.py
from fastapi import FastAPI, Header, HTTPException, Depends
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from passlib.context import CryptContext
from dotenv import load_dotenv
from ai import ask_ai, build_context
import psycopg2
import jwt
import datetime
import os

load_dotenv()

app = FastAPI()
SECRET = os.getenv("SECRET_KEY", "yellow_ai_secret")
pwd_context = CryptContext(schemes=["sha256_crypt"], deprecated="auto")

# ====== DB ======
def get_db():
    try:
        return psycopg2.connect(
            dbname=os.getenv("DB_NAME"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            host=os.getenv("DB_HOST"),
            port=os.getenv("DB_PORT", "5432")
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DB connection failed: {str(e)}")

# ====== Token ======
def verify_token(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="No token")
    try:
        token = authorization.split(" ")[1]
        return jwt.decode(token, SECRET, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

# ====== Memory ======
def save_message(username: str, message: str, role: str):
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO messages (username, role, message) VALUES (%s, %s, %s)",
            (username, role, message)
        )
        conn.commit()
    finally:
        cur.close()
        conn.close()

def get_history(username: str):
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT role, message FROM messages WHERE username=%s ORDER BY id DESC LIMIT 10",
            (username,)
        )
        return list(reversed(cur.fetchall()))
    finally:
        cur.close()
        conn.close()

# ====== Models ======
class User(BaseModel):
    username: str
    password: str

class ChatRequest(BaseModel):
    message: str

# ====== Routes ======
@app.get("/")
def home():
    return {"status": "Yellow AI 🚀"}

@app.post("/register", status_code=201)
def register(user: User):
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id FROM users WHERE username=%s", (user.username,))
        if cur.fetchone():
            raise HTTPException(status_code=400, detail="Username already exists")
        hashed = pwd_context.hash(user.password)
        cur.execute(
            "INSERT INTO users (username, password) VALUES (%s, %s)",
            (user.username, hashed)
        )
        conn.commit()
        return {"msg": "User created ✅"}
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cur.close()
        conn.close()

@app.post("/login")
def login(user: User):
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, password FROM users WHERE username=%s", (user.username,))
        result = cur.fetchone()
        if not result or not pwd_context.verify(user.password, result[1]):
            raise HTTPException(status_code=401, detail="Invalid credentials")
        token = jwt.encode(
            {
                "user_id": result[0],
                "username": user.username,
                "exp": datetime.datetime.utcnow() + datetime.timedelta(days=7)
            },
            SECRET,
            algorithm="HS256"
        )
        return {"msg": "Login success 🚀", "access_token": token}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cur.close()
        conn.close()

@app.get("/me")
def me(user=Depends(verify_token)):
    return {"user_id": user["user_id"], "username": user["username"]}

@app.post("/chat")
def chat(req: ChatRequest, user=Depends(verify_token)):
    username = user["username"]
    save_message(username, req.message, "user")
    history = get_history(username)
    context = build_context(history)
    reply = ask_ai(req.message, context)
    save_message(username, reply, "assistant")
    return {
        "input": req.message,
        "response": reply
    }

@app.get("/ui", response_class=HTMLResponse)
def ui():
    with open("templates/index.html", encoding="utf-8") as f:
        return f.read()
