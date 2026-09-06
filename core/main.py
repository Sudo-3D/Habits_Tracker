from flask import Flask, request, jsonify, session
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import os

app = Flask(__name__)
# مفتاح سري لتشفير الـ Sessions المحفوظة في المتصفح
app.secret_key = "habit_tracker_super_secret_key"

# السماح للواجهة بالتعامل مع البيانات والجلسات عبر CORS
CORS(app, supports_credentials=True)

DB_PATH = "habits.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 1. إنشاء جدول المستخدمين
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # 2. إنشاء جدول العادات مضافاً إليه user_id
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS habits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            name TEXT,
            time TEXT,
            ai_tips TEXT,
            ai_question TEXT,
            streak INTEGER DEFAULT 0,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    """)
    
    # 3. إنشاء جدول حفظ محادثات الـ AI
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chat_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            sender TEXT NOT NULL,
            message TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    conn.commit()
    conn.close()

init_db()

# ----------------- Auth Endpoints -----------------

@app.route("/register", methods=["POST"])
def register():
    data = request.json or {}
    email = data.get("email", "").strip().lower()
    password = data.get("password")

    if not email or not password:
        return jsonify({"error": "Email and password are required"}), 400

    hashed_pw = generate_password_hash(password)

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO users (email, password_hash) VALUES (?, ?)", (email, hashed_pw))
        conn.commit()
        conn.close()
        return jsonify({"message": "User registered successfully"}), 201
    except sqlite3.IntegrityError:
        return jsonify({"error": "Email already exists"}), 400

@app.route("/login", methods=["POST"])
def login():
    data = request.json or {}
    email = data.get("email", "").strip().lower()
    password = data.get("password")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, password_hash FROM users WHERE email = ?", (email,))
    user = cursor.fetchone()
    conn.close()

    if user and check_password_hash(user[1], password):
        session["user_id"] = user[0]
        return jsonify({"message": "Logged in successfully", "user_id": user[0]})
    
    return jsonify({"error": "Invalid email or password"}), 401

@app.route("/logout", methods=["POST"])
def logout():
    session.pop("user_id", None)
    return jsonify({"message": "Logged out successfully"})

# ----------------- Habits Endpoints -----------------

@app.route("/habits", methods=["GET"])
def get_habits():
    user_id = request.args.get("user_id") or session.get("user_id")
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    if user_id:
        cursor.execute("SELECT id, name, time, ai_tips, ai_question, streak FROM habits WHERE user_id = ?", (user_id,))
    else:
        cursor.execute("SELECT id, name, time, ai_tips, ai_question, streak FROM habits")
        
    rows = cursor.fetchall()
    conn.close()
    return jsonify([{"id": r[0], "name": r[1], "time": r[2], "ai_tips": r[3], "ai_question": r[4], "streak": r[5]} for r in rows])

@app.route("/habits", methods=["POST"])
def add_habit():
    data = request.json or {}
    user_id = data.get("user_id") or session.get("user_id")
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO habits (user_id, name, time, ai_tips, ai_question) VALUES (?, ?, ?, ?, ?)",
        (user_id, data.get("name"), data.get("time"), data.get("ai_tips", ""), data.get("ai_question", ""))
    )
    conn.commit()
    conn.close()
    return jsonify({"status": "success"})

@app.route("/habits/<int:habit_id>/increment", methods=["POST"])
def increment_streak(habit_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE habits SET streak = streak + 1 WHERE id = ?", (habit_id,))
    conn.commit()
    conn.close()
    return jsonify({"status": "streak updated", "id": habit_id})

@app.route("/habits/<int:habit_id>", methods=["DELETE"])
def delete_habit(habit_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM habits WHERE id = ?", (habit_id,))
    conn.commit()
    conn.close()
    return jsonify({"status": "deleted", "id": habit_id})

@app.route("/habits/<int:habit_id>", methods=["PUT"])
def update_habit(habit_id):
    data = request.json or {}
    name = data.get("name")
    time = data.get("time")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE habits SET name = ?, time = ? WHERE id = ?", (name, time, habit_id))
    conn.commit()
    conn.close()

    return jsonify({"success": True, "message": "Habit updated successfully"})

# ----------------- Chat History Endpoints -----------------

@app.route("/chat/save", methods=["POST"])
def save_chat_message():
    data = request.json or {}
    session_id = data.get("session_id")
    sender = data.get("sender")
    message = data.get("message")

    if not session_id or not sender or not message:
        return jsonify({"error": "Missing parameters"}), 400

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO chat_history (session_id, sender, message) VALUES (?, ?, ?)",
        (session_id, sender, message)
    )
    conn.commit()
    conn.close()
    return jsonify({"status": "success"})

@app.route("/chat/history/<session_id>", methods=["GET"])
def get_chat_history(session_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT sender, message, timestamp FROM chat_history WHERE session_id = ? ORDER BY id ASC",
        (session_id,)
    )
    rows = cursor.fetchall()
    conn.close()

    history = [{"sender": r[0], "message": r[1], "timestamp": r[2]} for r in rows]
    return jsonify(history)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8040, debug=False)