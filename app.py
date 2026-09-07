import os
import secrets
import sqlite3
import time
from pathlib import Path
from datetime import datetime

from flask import (
Flask,
render_template,
request,
jsonify,
send_from_directory,
abort,
session,
redirect,
url_for
)
from werkzeug.utils import secure_filename
import qrcode

BASE = Path(__file__).resolve().parent
UPLOADS = BASE / "uploads"
STATIC = BASE / "static"
UPLOADS.mkdir(exist_ok=True)
STATIC.mkdir(exist_ok=True)

DB = BASE / "qrshare.db"

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", secrets.token_hex(32))

# Maximum upload size: 1 GB

app.config["MAX_CONTENT_LENGTH"] = 1024 * 1024 * 1024

def db():
con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row
return con

def init():
con = db()

```
con.executescript("""
CREATE TABLE IF NOT EXISTS rooms (
    id TEXT PRIMARY KEY,
    password TEXT,
    created REAL,
    expires REAL
);

CREATE TABLE IF NOT EXISTS files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    room_id TEXT,
    stored_name TEXT,
    original_name TEXT,
    size INTEGER,
    created REAL
);
""")

con.commit()
con.close()
```

def clean_expired():
con = db()

```
rows = con.execute(
    "SELECT id FROM rooms WHERE expires < ?",
    (time.time(),)
).fetchall()

for row in rows:
    room_id = row["id"]

    files = con.execute(
        "SELECT stored_name FROM files WHERE room_id=?",
        (room_id,)
    ).fetchall()

    for file in files:
        path = UPLOADS / file["stored_name"]

        if path.exists():
            path.unlink()

    con.execute(
        "DELETE FROM files WHERE room_id=?",
        (room_id,)
    )

    con.execute(
        "DELETE FROM rooms WHERE id=?",
        (room_id,)
    )

con.commit()
con.close()
```

def generate_room_id():
return secrets.token_urlsafe(6).replace("-", "").replace("_", "")[:8].upper()

@app.before_request
def housekeeping():
clean_expired()

@app.route("/")
def home():
return render_template("home.html")

@app.post("/create")
def create():
password = request.form.get("password", "").strip()

```
try:
    hours = int(request.form.get("hours", "24"))
except ValueError:
    hours = 24

hours = min(max(hours, 1), 168)

room_id = generate_room_id()

con = db()

con.execute(
    "INSERT INTO rooms VALUES (?, ?, ?, ?)",
    (
        room_id,
        password,
        time.time(),
        time.time() + hours * 3600
    )
)

con.commit()
con.close()

return redirect(url_for("room", room_id=room_id))
```

@app.post("/join")
def join():
room_id = request.form.get("room_id", "").strip().upper()
password = request.form.get("password", "").strip()

```
con = db()

room = con.execute(
    "SELECT * FROM rooms WHERE id=?",
    (room_id,)
).fetchone()

con.close()

if not room:
    return render_template(
        "home.html",
        error="Room not found. Please check the Room ID."
    )

# If password protected, verify password
if room["password"]:
    if password != room["password"]:
        return render_template(
            "home.html",
            error="Incorrect password."
        )

    # Save authorization in browser session
    session[f"room_{room_id}"] = room["password"]

return redirect(url_for("room", room_id=room_id))
```

@app.route("/room/<room_id>", methods=["GET", "POST"])
def room(room_id):

```
room_id = room_id.upper()

con = db()

room_data = con.execute(
    "SELECT * FROM rooms WHERE id=?",
    (room_id,)
).fetchone()

con.close()

if not room_data:
    abort(404)

# Password protection
if room_data["password"]:

    session_key = f"room_{room_id}"

    if session.get(session_key) != room_data["password"]:

        if (
            request.method == "POST"
            and request.form.get("password")
            == room_data["password"]
        ):
            session[session_key] = room_data["password"]

            return redirect(
                url_for("room", room_id=room_id)
            )

        return render_template(
            "password.html",
            room_id=room_id
        )

# Generate QR code
share_url = request.url

qr = qrcode.make(share_url)

qr_filename = f"qr_{room_id}.png"

qr.save(STATIC / qr_filename)

expires = datetime.fromtimestamp(
    room_data["expires"]
).strftime("%d %b %Y, %I:%M %p")

return render_template(
    "room.html",
    room_id=room_id,
    share_url=share_url,
    expires=expires
)
```

@app.get("/api/room/<room_id>/files")
def list_files(room_id):

```
room_id = room_id.upper()

con = db()

rows = con.execute(
    """
    SELECT id, original_name, size, created
    FROM files
    WHERE room_id=?
    ORDER BY id DESC
    """,
    (room_id,)
).fetchall()

con.close()

return jsonify([dict(row) for row in rows])
```

@app.post("/api/room/<room_id>/upload")
def upload(room_id):

```
room_id = room_id.upper()

con = db()

room_data = con.execute(
    "SELECT * FROM rooms WHERE id=?",
    (room_id,)
).fetchone()

if not room_data:
    con.close()
    abort(404)

# Check password authorization
if (
    room_data["password"]
    and session.get(f"room_{room_id}")
    != room_data["password"]
):
    con.close()
    abort(403)

saved = []

for file in request.files.getlist("files"):

    if not file or not file.filename:
        continue

    original_name = secure_filename(file.filename)

    if not original_name:
        original_name = "file"

    stored_name = (
        secrets.token_hex(16)
        + "_"
        + original_name
    )

    path = UPLOADS / stored_name

    file.save(path)

    con.execute(
        """
        INSERT INTO files
        (room_id, stored_name, original_name, size, created)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            room_id,
            stored_name,
            original_name,
            path.stat().st_size,
            time.time()
        )
    )

    saved.append(original_name)

con.commit()
con.close()

return jsonify({
    "ok": True,
    "saved": saved
})
```

@app.get("/download/[int:file_id](int:file_id)")
def download(file_id):

```
con = db()

file_data = con.execute(
    "SELECT * FROM files WHERE id=?",
    (file_id,)
).fetchone()

con.close()

if not file_data:
    abort(404)

return send_from_directory(
    UPLOADS,
    file_data["stored_name"],
    as_attachment=True,
    download_name=file_data["original_name"]
)
```

@app.delete("/api/file/[int:file_id](int:file_id)")
def delete(file_id):

```
con = db()

file_data = con.execute(
    "SELECT * FROM files WHERE id=?",
    (file_id,)
).fetchone()

if not file_data:
    con.close()
    abort(404)

room_data = con.execute(
    "SELECT * FROM rooms WHERE id=?",
    (file_data["room_id"],)
).fetchone()

# Check permission
if (
    room_data["password"]
    and session.get(f"room_{room_data['id']}")
    != room_data["password"]
):
    con.close()
    abort(403)

path = UPLOADS / file_data["stored_name"]

if path.exists():
    path.unlink()

con.execute(
    "DELETE FROM files WHERE id=?",
    (file_id,)
)

con.commit()
con.close()

return jsonify({"ok": True})
```

init()

if **name** == "**main**":
port = int(os.environ.get("PORT", 5000))

```
app.run(
    host="0.0.0.0",
    port=port,
    debug=False
)
```
