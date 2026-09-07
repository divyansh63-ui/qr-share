import os, secrets, sqlite3, time
from pathlib import Path
from datetime import datetime, timedelta
from flask import Flask, render_template, request, jsonify, send_from_directory, abort, session, redirect, url_for
from werkzeug.utils import secure_filename
import qrcode

BASE = Path(__file__).resolve().parent
UPLOADS = BASE / "uploads"
UPLOADS.mkdir(exist_ok=True)
DB = BASE / "qrshare.db"

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", secrets.token_hex(32))
app.config["MAX_CONTENT_LENGTH"] = 1024 * 1024 * 1024  # 1 GB

def db():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con

def init():
    con = db()
    con.executescript("""
    CREATE TABLE IF NOT EXISTS rooms (
      id TEXT PRIMARY KEY, password TEXT, created REAL, expires REAL
    );
    CREATE TABLE IF NOT EXISTS files (
      id INTEGER PRIMARY KEY AUTOINCREMENT, room_id TEXT, stored_name TEXT,
      original_name TEXT, size INTEGER, created REAL
    );
    """)
    con.commit(); con.close()

def clean_expired():
    con = db()
    rows = con.execute("SELECT id FROM rooms WHERE expires < ?", (time.time(),)).fetchall()
    for row in rows:
        fs = con.execute("SELECT stored_name FROM files WHERE room_id=?", (row["id"],)).fetchall()
        for f in fs:
            p = UPLOADS / f["stored_name"]
            if p.exists(): p.unlink()
        con.execute("DELETE FROM files WHERE room_id=?", (row["id"],))
        con.execute("DELETE FROM rooms WHERE id=?", (row["id"],))
    con.commit(); con.close()

def room_id():
    return secrets.token_urlsafe(6).replace("-","").replace("_","")[:8].upper()

@app.before_request
def housekeeping():
    clean_expired()

@app.route("/")
def home():
    return render_template("home.html")

@app.post("/create")
def create():
    password = request.form.get("password","").strip()
    hours = min(max(int(request.form.get("hours", "24")), 1), 168)
    rid = room_id()
    con = db()
    con.execute("INSERT INTO rooms VALUES (?,?,?,?)",
                (rid, password, time.time(), time.time()+hours*3600))
    con.commit(); con.close()
    return redirect(url_for("room", room_id=rid))
    @app.post("/join")
def join():
    room_id = request.form.get("room_id", "").strip().upper()
    password = request.form.get("password", "").strip()

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

    # Check password if room is protected
    if room["password"]:
        if password != room["password"]:
            return render_template(
                "home.html",
                error="Incorrect password."
            )

        # Save access in session
        session[f"room_{room_id}"] = room["password"]

    return redirect(url_for("room", room_id=room_id))

@app.route("/room/<room_id>", methods=["GET","POST"])
def room(room_id):
    con=db(); r=con.execute("SELECT * FROM rooms WHERE id=?", (room_id,)).fetchone(); con.close()
    if not r: abort(404)
    if r["password"]:
        key=f"room_{room_id}"
        if session.get(key) != r["password"]:
            if request.method=="POST" and request.form.get("password")==r["password"]:
                session[key]=r["password"]
                return redirect(url_for("room",room_id=room_id))
            return render_template("password.html", room_id=room_id)
    url=request.url
    qr=qrcode.make(url)
    qr_path=Path("static")/f"qr_{room_id}.png"
    qr.save(BASE/qr_path)
    return render_template("room.html", room_id=room_id, share_url=url, expires=datetime.fromtimestamp(r["expires"]).strftime("%d %b %Y, %I:%M %p"))

@app.get("/api/room/<room_id>/files")
def list_files(room_id):
    con=db()
    rows=con.execute("SELECT id,original_name,size,created FROM files WHERE room_id=? ORDER BY id DESC",(room_id,)).fetchall()
    con.close()
    return jsonify([dict(x) for x in rows])

@app.post("/api/room/<room_id>/upload")
def upload(room_id):
    con=db(); room=con.execute("SELECT * FROM rooms WHERE id=?",(room_id,)).fetchone()
    if not room: con.close(); abort(404)
    if room["password"] and session.get(f"room_{room_id}") != room["password"]:
        con.close(); abort(403)
    saved=[]
    for f in request.files.getlist("files"):
        if not f or not f.filename: continue
        original=secure_filename(f.filename) or "file"
        stored=secrets.token_hex(16)+"_"+original
        path=UPLOADS/stored
        f.save(path)
        con.execute("INSERT INTO files(room_id,stored_name,original_name,size,created) VALUES(?,?,?,?,?)",
                    (room_id,stored,original,path.stat().st_size,time.time()))
        saved.append(original)
    con.commit(); con.close()
    return jsonify({"ok":True,"saved":saved})

@app.get("/download/<int:file_id>")
def download(file_id):
    con=db(); f=con.execute("SELECT * FROM files WHERE id=?",(file_id,)).fetchone(); con.close()
    if not f: abort(404)
    return send_from_directory(UPLOADS,f["stored_name"],as_attachment=True,download_name=f["original_name"])

@app.delete("/api/file/<int:file_id>")
def delete(file_id):
    con=db(); f=con.execute("SELECT * FROM files WHERE id=?",(file_id,)).fetchone()
    if not f: con.close(); abort(404)
    room=con.execute("SELECT * FROM rooms WHERE id=?",(f["room_id"],)).fetchone()
    if room["password"] and session.get(f"room_{room['id']}") != room["password"]:
        con.close(); abort(403)
    p=UPLOADS/f["stored_name"]
    if p.exists(): p.unlink()
    con.execute("DELETE FROM files WHERE id=?",(file_id,)); con.commit(); con.close()
    return jsonify({"ok":True})

init()

if __name__=="__main__":
    app.run(host="0.0.0.0",port=int(os.environ.get("PORT",5000)),debug=False)
