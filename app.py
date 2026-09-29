import os, sqlite3
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, abort

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-secret-before-deploying")
DB = os.environ.get("DATABASE_PATH", "tournaments.db")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "change-me")

def db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with db() as con:
        con.execute("""CREATE TABLE IF NOT EXISTS tournaments (
            id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL,
            game_mode TEXT NOT NULL, match_time TEXT NOT NULL,
            entry_type TEXT NOT NULL DEFAULT 'Free', prize TEXT NOT NULL DEFAULT '—',
            room_id TEXT DEFAULT '', room_password TEXT DEFAULT '', status TEXT NOT NULL DEFAULT 'Open'
        )""")
        con.execute("""CREATE TABLE IF NOT EXISTS players (
            id INTEGER PRIMARY KEY AUTOINCREMENT, tournament_id INTEGER NOT NULL,
            player_name TEXT NOT NULL, ff_uid TEXT NOT NULL, contact TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(tournament_id, ff_uid),
            FOREIGN KEY(tournament_id) REFERENCES tournaments(id)
        )""")

def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("admin"):
            return redirect(url_for("admin_login"))
        return fn(*args, **kwargs)
    return wrapper

@app.route("/")
def index():
    with db() as con:
        tournaments = con.execute("SELECT t.*, (SELECT COUNT(*) FROM players p WHERE p.tournament_id=t.id) AS player_count FROM tournaments t ORDER BY t.id DESC").fetchall()
    return render_template("index.html", tournaments=tournaments)

@app.route("/tournament/<int:tid>")
def tournament(tid):
    with db() as con:
        t = con.execute("SELECT * FROM tournaments WHERE id=?", (tid,)).fetchone()
        if not t: abort(404)
        players = con.execute("SELECT player_name, ff_uid, created_at FROM players WHERE tournament_id=? ORDER BY id", (tid,)).fetchall()
    show_room = bool(session.get("admin"))
    return render_template("tournament.html", t=t, players=players, show_room=show_room)

@app.route("/join/<int:tid>", methods=["POST"])
def join(tid):
    name = request.form.get("player_name", "").strip()[:60]
    uid = request.form.get("ff_uid", "").strip()[:40]
    contact = request.form.get("contact", "").strip()[:100]
    if not name or not uid:
        flash("Enter your in-game name and Free Fire UID.", "error")
        return redirect(url_for("tournament", tid=tid))
    with db() as con:
        t = con.execute("SELECT status FROM tournaments WHERE id=?", (tid,)).fetchone()
        if not t: abort(404)
        if t["status"] != "Open":
            flash("Registration is closed for this tournament.", "error")
        else:
            try:
                con.execute("INSERT INTO players (tournament_id, player_name, ff_uid, contact) VALUES (?,?,?,?)", (tid, name, uid, contact))
                flash("Registration successful! Check the tournament page for updates.", "success")
            except sqlite3.IntegrityError:
                flash("This UID is already registered for this tournament.", "error")
    return redirect(url_for("tournament", tid=tid))

@app.route("/admin", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        if request.form.get("password", "") == ADMIN_PASSWORD:
            session["admin"] = True
            return redirect(url_for("admin_dashboard"))
        flash("Incorrect admin password.", "error")
    return render_template("admin_login.html")

@app.route("/admin/dashboard")
@admin_required
def admin_dashboard():
    with db() as con:
        tournaments = con.execute("SELECT t.*, (SELECT COUNT(*) FROM players p WHERE p.tournament_id=t.id) AS player_count FROM tournaments t ORDER BY t.id DESC").fetchall()
    return render_template("admin.html", tournaments=tournaments)

@app.route("/admin/create", methods=["POST"])
@admin_required
def create_tournament():
    title = request.form.get("title", "").strip()[:100]
    mode = request.form.get("game_mode", "Squad")
    match_time = request.form.get("match_time", "").strip()
    prize = request.form.get("prize", "—").strip()[:100]
    if not title or not match_time:
        flash("Tournament title and match time are required.", "error")
        return redirect(url_for("admin_dashboard"))
    if mode not in ("Solo", "Duo", "Squad"): mode = "Squad"
    with db() as con:
        con.execute("INSERT INTO tournaments (title, game_mode, match_time, prize) VALUES (?,?,?,?)", (title, mode, match_time, prize))
    flash("Tournament created.", "success")
    return redirect(url_for("admin_dashboard"))

@app.route("/admin/tournament/<int:tid>", methods=["POST"])
@admin_required
def update_tournament(tid):
    room_id = request.form.get("room_id", "").strip()[:80]
    room_password = request.form.get("room_password", "").strip()[:80]
    status = request.form.get("status", "Open")
    if status not in ("Open", "Closed", "Completed"): status = "Open"
    with db() as con:
        con.execute("UPDATE tournaments SET room_id=?, room_password=?, status=? WHERE id=?", (room_id, room_password, status, tid))
    flash("Tournament details updated.", "success")
    return redirect(url_for("admin_dashboard"))

@app.route("/admin/logout")
def admin_logout():
    session.clear()
    return redirect(url_for("index"))

@app.route("/health")
def health():
    return {"status": "ok"}

init_db()
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)
