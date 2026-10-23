import os

from dotenv import load_dotenv
from flask import Flask, abort, jsonify, request, send_from_directory, session

# Your Supabase class (save it next to this file as account.py)
from account import Account

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Flask serves everything in the "static" folder at /static/... automatically.
app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-only-change-me")
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    # SESSION_COOKIE_SECURE=True,  # turn on once the site is served over HTTPS
)

MIN_PASSWORD_LENGTH = 8

# Only these HTML files can be requested. Add new pages here as you build them.
PAGES = {"index.html", "about.html"}


def body():
    """Return the JSON body of the request as a dict (empty if missing or invalid)."""
    return request.get_json(silent=True) or {}


# ---------- Pages ----------

@app.get("/")
def home():
    return send_from_directory(BASE_DIR, "index.html")


@app.get("/about")
def about():
    return send_from_directory(BASE_DIR, "about.html")


@app.get("/<name>.html")
def page(name):
    filename = f"{name}.html"
    if filename not in PAGES:
        abort(404)
    return send_from_directory(BASE_DIR, filename)


# ---------- API ----------

@app.post("/api/signup")
def signup():
    data = body()
    email = (data.get("email") or "").strip()
    password = data.get("password") or ""
    first_name = (data.get("first_name") or "").strip()
    last_name = (data.get("last_name") or "").strip()
    phone = (data.get("phone") or "").strip()

    if not email or not first_name or not last_name:
        return jsonify(ok=False, error="Please fill in all required fields."), 400
    if len(password) < MIN_PASSWORD_LENGTH:
        return jsonify(
            ok=False,
            error=f"Password must be at least {MIN_PASSWORD_LENGTH} characters.",
        ), 400

    # A fresh Account() per request keeps one user's Supabase session
    # from ever being shared with another user's request.
    created = Account().create_account(email, password, first_name, last_name, phone)
    if not created:
        return jsonify(
            ok=False,
            error="We couldn't create that account. The email may already be in use.",
        ), 400
    return jsonify(ok=True)


@app.post("/api/login")
def login():
    data = body()
    email = (data.get("email") or "").strip()
    password = data.get("password") or ""

    if not email or not password:
        return jsonify(ok=False, error="Enter your email and password."), 400

    ok, role, supa_session = Account().login(email, password)
    if not ok:
        return jsonify(ok=False, error="Invalid email or password."), 401

    session.clear()
    session["user_id"] = supa_session.user.id
    session["role"] = role
    return jsonify(ok=True, role=role)


@app.post("/api/logout")
def logout():
    session.clear()
    return jsonify(ok=True)


@app.post("/api/reset-password")
def reset_password():
    email = (body().get("email") or "").strip()
    if email:
        Account().reset_password(email)
    # Always answer the same way so the form can't be used to find out
    # which emails have accounts.
    return jsonify(ok=True)


@app.get("/api/me")
def me():
    if "user_id" not in session:
        return jsonify(logged_in=False)
    return jsonify(logged_in=True, role=session.get("role"))


if __name__ == "__main__":
    app.run(debug=True)
