from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    send_file
)
import sqlite3
import os
from datetime import datetime
import csv
from werkzeug.security import generate_password_hash, check_password_hash

# ---------------- APP CONFIG ----------------
app = Flask(__name__)
app.secret_key = "labwork_secret_key"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "database.db")

# ---------------- DB CONNECTION ----------------
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# ---------------- INIT DB ----------------
def init_db():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT,
        role TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS work_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT,
        category TEXT,
        work TEXT,
        comment TEXT,
        date TEXT,
        time TEXT
    )
    """)

    # ADMIN USER
    cur.execute("""
    INSERT OR IGNORE INTO users (username,password,role)
    VALUES (?,?,?)
    """, ("admin", generate_password_hash("1234"), "admin"))

    conn.commit()
    conn.close()
    # ---------------- Helper Functions ----------------
    # ---------------- Helper Functions ----------------
def is_admin():
    """Check if logged-in user is admin"""
    return "role" in session and session["role"] == "admin"

# ---------------- LOGIN ----------------
@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE username=?", (username,))
        user = cur.fetchone()
        conn.close()

        if user and check_password_hash(user["password"], password):

            session["username"] = user["username"]
            session["role"] = user["role"]            
            return redirect(url_for("dashboard"))

        return render_template("login.html", error="Invalid Login ❌")

    return render_template("login.html")

# ---------------- DASHBOARD ----------------
@app.route('/dashboard')
def dashboard():
    import sqlite3

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    category_name = request.args.get('category')

    if not category_name:
        cur.execute("SELECT * FROM work_log")
    else:
        cur.execute(
            "SELECT * FROM work_log WHERE category = ?",
            (category_name,)
        )

    data = cur.fetchall()
    conn.close()

    return render_template("dashboard.html", data=data)
# ---------------- CATEGORY ----------------
@app.route("/category/<category_name>", methods=["GET", "POST"])
def category(category_name):
    if "username" not in session:
        return redirect(url_for("login"))

    conn = get_db()
    cur = conn.cursor()

    if request.method == "POST":
        work = request.form["work"]
        comment = request.form.get("comment", "")
        now = datetime.now()

        cur.execute("""
            INSERT INTO work_log (username, category, work, comment, date, time)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            session["username"],
            category_name,
            work,
            comment,
            now.strftime("%Y-%m-%d"),
            now.strftime("%H:%M:%S")
        ))
        conn.commit()

    if session.get("role") == "admin":
        cur.execute("""
            SELECT * FROM work_log
            WHERE category=?
            ORDER BY id DESC
        """, (category_name,))
    else:
        cur.execute("""
            SELECT * FROM work_log
            WHERE category=? AND username=?
            ORDER BY id DESC
        """, (category_name, session["username"]))

    records = cur.fetchall()
    conn.close()

    return render_template(
        "category.html",
        category_name=category_name,
        records=records
    )

# ---------------- CHANGE PASSWORD ----------------
@app.route('/change_password', methods=['GET', 'POST'])
def change_password():
    if request.method == 'POST':
        old_password = request.form.get('old_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')

        if not old_password or not new_password or not confirm_password:
            return render_template(
                'change_password.html',
                error="All fields are required"
            )

        conn = sqlite3.connect('database.db')
        cur = conn.cursor()

        cur.execute(
            "SELECT password FROM users WHERE username = ?",
            (session['username'],)
        )
        row = cur.fetchone()

        if not row:
            conn.close()
            return render_template(
                'change_password.html',
                error="User not found"
            )

        db_password = row[0]

        # 🔐 Old password check
        if not check_password_hash(db_password, old_password):
            conn.close()
            return render_template(
                'change_password.html',
                error="Old password incorrect"
            )

        # 🔁 New password match check
        if new_password != confirm_password:
            conn.close()
            return render_template(
                'change_password.html',
                error="New password mismatch"
            )

        # ✅ Update password
        hashed = generate_password_hash(new_password)

        cur.execute(
            "UPDATE users SET password = ? WHERE username = ?",
            (hashed, session['username'])
        )
        conn.commit()
        conn.close()

        return render_template(
            'change_password.html',
            msg="Password changed successfully ✅"
        )

    return render_template('change_password.html')


# ---------------- DOWNLOAD EXCEL (ADMIN ONLY) ----------------
@app.route("/download_excel")
def download_excel():
    if "username" not in session or session["role"] != "admin":
        return redirect(url_for("login"))

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT username, date, time, category, work, comment
        FROM work_log
        ORDER BY date DESC, time DESC
    """)
    rows = cur.fetchall()
    conn.close()

    filename = "lab_work_report.csv"

    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Username", "Date", "Time", "Category", "Work", "Comment"])
        for r in rows:
            writer.writerow([
                r["username"],
                r["date"],
                r["time"],
                r["category"],
                r["work"],
                r["comment"]
            ])

    return send_file(filename, as_attachment=True)
@app.route("/admin/change_username", methods=["GET", "POST"])
def admin_change_username():
    if not is_admin():
        return redirect(url_for("login"))

    message = None
    error = None

    if request.method == "POST":
        old_username = request.form["old_username"]
        new_username = request.form["new_username"]

        conn = sqlite3.connect("database.db")
        cur = conn.cursor()

        # old username exists?
        cur.execute("SELECT * FROM users WHERE username=?", (old_username,))
        user = cur.fetchone()

        if not user:
            error = "Old username not found"
        else:
            try:
                cur.execute(
                    "UPDATE users SET username=? WHERE username=?",
                    (new_username, old_username)
                )
                conn.commit()
                message = "Username updated successfully"
            except sqlite3.IntegrityError:
                error = "New username already exists"

        conn.close()

    return render_template(
        "admin_change_username.html",
        message=message,
        error=error
    )
@app.route('/admin/users')
def admin_users():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))

    conn = sqlite3.connect('database.db')
    cur = conn.cursor()

    cur.execute("SELECT id, username, role FROM users WHERE role = 'staff'")
    users = cur.fetchall()

    conn.close()
    return render_template('admin_user.html', users=users)

@app.route('/admin/reset/<int:user_id>', methods=['GET', 'POST'])
def admin_reset_password(user_id):
    if session.get('role') != 'admin':
        return redirect(url_for('login'))

    conn = sqlite3.connect('database.db')
    cur = conn.cursor()

    # ALWAYS fetch user
    cur.execute("SELECT id, username FROM users WHERE id = ?", (user_id,))
    user = cur.fetchone()

    if not user:
        conn.close()
        return "User not found", 404

    if request.method == 'POST':
        new_password = request.form.get('new_password')

        if not new_password:
            conn.close()
            return render_template(
                'admin_reset.html',
                user=user,
                error="Password required"
            )

        hashed = generate_password_hash(new_password)

        cur.execute(
            "UPDATE users SET password = ? WHERE id = ?",
            (hashed, user_id)
        )
        conn.commit()
        conn.close()

        return render_template(
            'admin_reset.html',
            user=user,
            msg="Password reset successful ✅"
        )

    conn.close()
    return render_template('admin_reset.html', user=user)
# ---------------- LOGOUT ----------------
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/forgot_password", methods=["GET", "POST"])
def forgot_password():
    return render_template("forgot_password.html")

# ---------------- RUN ----------------
if __name__ == "__main__":
    init_db()   # first run only; later comment if needed
    app.run(host="10.10.131.36", port=5000, debug=True)