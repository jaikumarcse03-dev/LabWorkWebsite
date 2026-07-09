import sqlite3
from werkzeug.security import generate_password_hash

conn = sqlite3.connect("database.db")  # same DB path
cur = conn.cursor()

cur.execute("SELECT id, password FROM users")
users = cur.fetchall()

for uid, pwd in users:
    if not pwd.startswith("pbkdf2:"):
        hashed = generate_password_hash(pwd)
        cur.execute(
            "UPDATE users SET password=? WHERE id=?",
            (hashed, uid)
        )

conn.commit()
conn.close()

print("Password migration completed ✅")