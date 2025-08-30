from flask import Flask, request, jsonify
from flask_cors import CORS
import psycopg2
from psycopg2.extras import RealDictCursor
import smtplib
from email.mime.text import MIMEText
from werkzeug.security import generate_password_hash, check_password_hash

# ===== Flask setup =====
app = Flask(__name__)
CORS(app)

# ===== DB helpers =====
def get_db():
    return psycopg2.connect(
        host="localhost",
        database="nexcentdb",        # <-- உங்க PostgreSQL database name
        user="postgres",             # <-- உங்க PostgreSQL username
        password="postgres123",    # <-- உங்க PostgreSQL password
        cursor_factory=RealDictCursor
    )

def init_db():
    with get_db() as conn:
        cur = conn.cursor()
        # users table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL
            )
        """)
        # contacts table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS contacts (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                email TEXT NOT NULL,
                message TEXT NOT NULL
            )
        """)
        conn.commit()

# ===== Utils =====
def find_user_by_email(email: str):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id, name, email, password_hash FROM users WHERE email = %s", (email,))
        row = cur.fetchone()
        if not row:
            return None
        return {"id": row["id"], "name": row["name"], "email": row["email"], "password_hash": row["password_hash"]}

def send_admin_mail(sender_name: str, sender_email: str, message: str):
    SENDER_EMAIL = "manojkumar1612.cw@gmail.com"
    SENDER_APP_PASSWORD = "zdnmaworsxoufbpx"  # Gmail App Password
    ADMIN_EMAIL = "manojkumar1612.cw@gmail.com"

    subject = "New Contact Message"
    body = f"From: {sender_name} <{sender_email}>\n\n{message}"

    mime = MIMEText(body)
    mime["Subject"] = subject
    mime["From"] = SENDER_EMAIL
    mime["To"] = ADMIN_EMAIL

    server = smtplib.SMTP("smtp.gmail.com", 587)
    server.starttls()
    server.login(SENDER_EMAIL, SENDER_APP_PASSWORD)
    server.sendmail(SENDER_EMAIL, [ADMIN_EMAIL], mime.as_string())
    server.quit()

# ===== Routes =====
@app.route("/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip().lower()
    password = (data.get("password") or "").strip()

    if not name or not email or not password:
        return jsonify({"message": "Name, email and password required"}), 400

    if find_user_by_email(email):
        return jsonify({"message": "User already exists!"}), 400

    password_hash = generate_password_hash(password)

    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO users (name, email, password_hash) VALUES (%s, %s, %s)",
                (name, email, password_hash),
            )
            conn.commit()
        return jsonify({"message": f"User {email} registered successfully!"}), 201
    except Exception as e:
        return jsonify({"message": "Error creating user", "error": str(e)}), 400

@app.route("/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = (data.get("password") or "").strip()

    if not email or not password:
        return jsonify({"message": "Email and password required"}), 400

    user = find_user_by_email(email)
    if not user:
        return jsonify({"message": "Invalid email or password"}), 401

    if not check_password_hash(user["password_hash"], password):
        return jsonify({"message": "Invalid email or password"}), 401

    return jsonify({
        "message": "Login successful",
        "name": user["name"],
        "email": user["email"],
        "token": "dummy-jwt-token"
    }), 200

@app.route("/contact", methods=["POST"])
def contact():
    data = request.get_json(silent=True) or {}
    message = (data.get("message") or "").strip()

    if not message:
        return jsonify({"message": "Message is required"}), 400

    auth_email = (data.get("authEmail") or "").strip().lower()

    if auth_email:
        user = find_user_by_email(auth_email)
        if not user:
            return jsonify({"message": "Invalid logged-in user"}), 401
        name = user["name"]
        email = user["email"]
    else:
        name = (data.get("name") or "").strip()
        email = (data.get("email") or "").strip().lower()
        if not name or not email:
            return jsonify({"message": "Name & Email required for guests"}), 400

    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO contacts (name, email, message) VALUES (%s, %s, %s)",
            (name, email, message),
        )
        conn.commit()

    try:
        send_admin_mail(name, email, message)
        return jsonify({"message": "Your message has been sent to admin!"}), 200
    except Exception as e:
        return jsonify({"message": "Message saved, but email failed!", "error": str(e)}), 202

@app.route("/users", methods=["GET"])
def list_users():
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id, name, email FROM users")
        rows = cur.fetchall()
    return jsonify(rows), 200

@app.route("/contacts", methods=["GET"])
def list_contacts():
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id, name, email, message FROM contacts ORDER BY id DESC")
        rows = cur.fetchall()
    return jsonify(rows), 200

# ===== Run =====
if __name__ == "__main__":
    init_db()
    app.run(debug=True)
