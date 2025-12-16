import os
import json
import hashlib
import random
import sqlite3
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, send_from_directory

app = Flask(__name__)
app.secret_key = "3r4gdbhu3y43iqw"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
USER_FILE = os.path.join(BASE_DIR, "users.json")
DB_PATH = os.path.join(BASE_DIR, "users.db")

# -------------------------
# Theme-based images
# -------------------------
CHOCOLATES = {
    "1": "c1.webp", "2": "c2.jpg", "3": "c3.webp", "4": "c4.webp", "5": "c5.jpg",
    "6": "c6.jpg", "7": "c7.jpg", "8": "c8.webp", "9": "c9.jpg", "10": "c10.webp"
}
FLOWERS = {
    "1": "f1.webp", "2": "f2.jpg", "3": "f3.jpg", "4": "f4.webp", "5": "f5.jpeg",
    "6": "f6.jpg", "7": "f7.jpeg", "8": "f8.jpg", "9": "f9.webp", "10": "f10.jpg"
}
CARS = {
    "1": "car1.avif", "2": "car2.jpeg", "3": "car3.jpeg", "4": "car4.jpg", "5": "car5.jpeg",
    "6": "car6.webp", "7": "car7.webp", "8": "car8.jpg", "9": "car9.jpg", "10": "car10.jpg"
}
ANIMALS = {
    "1": "a1.jpg", "2": "a2.webp", "3": "a3.jpg", "4": "a4.jpg", "5": "a5.jpg",
    "6": "a6.avif", "7": "a7.jpg", "8": "a8.jpg", "9": "a9.jpg", "10": "a10.jpg"
}

IMAGES = {
    "chocolates": CHOCOLATES,
    "flowers": FLOWERS,
    "cars": CARS,
    "animals": ANIMALS
}

# -------------------------
# Utility Functions
# -------------------------
def get_users():
    if not os.path.exists(USER_FILE):
        return {}
    with open(USER_FILE, 'r') as f:
        return json.load(f)

def save_users(users):
    with open(USER_FILE, 'w') as f:
        json.dump(users, f, indent=4)

def hash_sequence(sequence):
    return hashlib.sha256(sequence.encode()).hexdigest()

def get_shuffled_images(theme="chocolates"):
    theme_dict = IMAGES.get(theme, {})
    image_items = list(theme_dict.items())
    random.shuffle(image_items)
    return image_items

# -------------------------
# Helper: log login attempt
# -------------------------
def log_login(username, success, method):
    """Log timestamped login attempt."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            INSERT INTO login_logs (username, method, success, timestamp)
            VALUES (?, ?, ?, ?)
        """, (username, method, int(success), datetime.now().isoformat()))
        conn.commit()

# -------------------------
# Failed login tracker for /login1
# -------------------------
def record_failed_attempt(email):
    """Increment failed attempts and set lock time if limit reached."""
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute("SELECT failed_count, last_failed FROM failed_logins WHERE email = ?", (email,))
        row = cur.fetchone()

        now = datetime.now()
        if row:
            failed_count, last_failed = row
            failed_count += 1
            if failed_count >= 3:
                # lock for 1 hour
                lock_until = now + timedelta(hours=1)
                cur.execute("""
                    UPDATE failed_logins
                    SET failed_count=?, lock_until=?
                    WHERE email=?
                """, (failed_count, lock_until.isoformat(), email))
            else:
                cur.execute("""
                    UPDATE failed_logins
                    SET failed_count=?, last_failed=?
                    WHERE email=?
                """, (failed_count, now.isoformat(), email))
        else:
            cur.execute("""
                INSERT INTO failed_logins (email, failed_count, last_failed)
                VALUES (?, ?, ?)
            """, (email, 1, now.isoformat()))
        conn.commit()

def reset_failed_attempts(email):
    """Reset failed attempts after successful login."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM failed_logins WHERE email = ?", (email,))
        conn.commit()

def is_account_locked(email):
    """Return True if account is locked, else False."""
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute("SELECT lock_until FROM failed_logins WHERE email = ?", (email,))
        row = cur.fetchone()
        if row and row[0]:
            lock_until = datetime.fromisoformat(row[0])
            if datetime.now() < lock_until:
                return True, lock_until
    return False, None

# -------------------------
# Routes
# -------------------------
@app.route('/')
@app.route('/home')
def home():
    return render_template('home.html')

@app.route('/contact')
def contact():
    return render_template('contact.html')

@app.route('/demo')
def demo():
    theme = request.args.get("theme") or "chocolates"
    images = get_shuffled_images(theme)
    return render_template('demo.html', images=images, theme=theme)

# -------------------------
# Graphical Password Registration
# -------------------------
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'GET':
        theme = request.args.get("theme") or "chocolates"
        images = get_shuffled_images(theme)
        return render_template('register.html', images=images, theme=theme)

    username = request.form.get('username')
    sequence = request.form.get('sequence')
    theme = request.form.get('theme') or "chocolates"

    if not username or not sequence:
        return f"<script>alert('Missing username or sequence!');window.location.href='/register?theme={theme}';</script>"

    users = get_users()
    if username in users:
        return f"<script>alert('User already exists. Please login instead!');window.location.href='/login?theme={theme}';</script>"

    users[username] = {
        'password_hash': hash_sequence(sequence),
        'sequence': sequence.split('-'),
        'theme': theme
    }
    save_users(users)

    return f"<script>alert('🎉 Registration successful! Please login now.');window.location.href='/login?theme={theme}';</script>"

# -------------------------
# Graphical Password Login
# -------------------------
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        theme = request.args.get("theme") or "chocolates"
        images = get_shuffled_images(theme)
        return render_template('login.html', images=images, theme=theme)

    username = request.form.get('username')
    sequence_attempt = request.form.get('sequence')
    theme = request.form.get('theme') or "chocolates"

    users = get_users()
    if username not in users:
        log_login(username, False, "graphical")
        return f"<script>alert('Invalid username!');window.location.href='/login?theme={theme}';</script>"

    hashed_attempt = hash_sequence(sequence_attempt)
    if hashed_attempt == users[username]['password_hash']:
        log_login(username, True, "graphical")
        return f"<script>alert('Welcome, {username}!');window.location.href='/last';</script>"
    else:
        log_login(username, False, "graphical")
        return f"<script>alert('Incorrect sequence/pattern!');window.location.href='/login?theme={theme}';</script>"

# -------------------------
# Classic Email/Password Login
# -------------------------
@app.route('/login1', methods=['GET', 'POST'])
def login1():
    if request.method == 'POST':
        email = request.form['username']
        password = request.form['password']
        password_hash = hashlib.sha256(password.encode()).hexdigest()

        locked, lock_until = is_account_locked(email)
        if locked:
            return f"""
            <script>
                alert("Your account is locked until {lock_until.strftime('%Y-%m-%d %H:%M:%S')} due to multiple failed attempts.");
                window.location.href = "/login1";
            </script>
            """

        with sqlite3.connect(DB_PATH) as conn:
            cur = conn.cursor()
            cur.execute("SELECT password FROM users WHERE email = ?", (email,))
            row = cur.fetchone()

        if row and row[0] == password_hash:
            reset_failed_attempts(email)
            log_login(email, True, "classic")
            return "<script>alert('Login successful ✅');window.location.href='/demo';</script>"
        else:
            record_failed_attempt(email)
            log_login(email, False, "classic")
            return "<script>alert('Invalid credentials. Please try again.');window.location.href='/login1';</script>"

    return render_template("login1.html")

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        fullname = request.form['fullname']
        email = request.form['email']
        password = request.form['password']
        password_hash = hashlib.sha256(password.encode()).hexdigest()

        try:
            with sqlite3.connect(DB_PATH) as conn:
                cur = conn.cursor()
                cur.execute(
                    "INSERT INTO users (fullname, email, password) VALUES (?, ?, ?)",
                    (fullname, email, password_hash)
                )
                conn.commit()
        except sqlite3.IntegrityError:
            return "<script>alert('Email already exists.');window.location.href='/signup';</script>"

        return "<script>alert('Account created successfully ✅');window.location.href='/login1';</script>"

    return render_template('signup.html')

@app.route('/last')
def last():
    return render_template('last.html')

@app.route('/templates/<path:filename>')
def serve_templates_file(filename):
    return send_from_directory(os.path.join(BASE_DIR, 'templates'), filename)

# -------------------------
# 🪵 Admin Route: View Login Logs
# -------------------------
@app.route("/admin/logs")
def show_logs():
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM login_logs ORDER BY id DESC LIMIT 20")
        logs = cur.fetchall()

    html = "<h2>🪵 Recent Login Logs</h2><table border='1' cellpadding='6'>"
    html += "<tr><th>ID</th><th>Username</th><th>Method</th><th>Success</th><th>Timestamp</th></tr>"
    for log in logs:
        id, username, method, success, timestamp = log
        status = "✅" if success else "❌"
        html += f"<tr><td>{id}</td><td>{username}</td><td>{method}</td><td>{status}</td><td>{timestamp}</td></tr>"
    html += "</table>"
    return html

# -------------------------
# Database setup
# -------------------------
def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fullname TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                password TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS login_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT,
                method TEXT,
                success INTEGER,
                timestamp TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS failed_logins (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE,
                failed_count INTEGER DEFAULT 0,
                last_failed TEXT,
                lock_until TEXT
            )
        """)
init_db()

# -------------------------
# Run App
# -------------------------
if __name__ == '__main__':
    app.run(debug=True)
