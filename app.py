import os
import re
import sqlite3
from functools import wraps
from urllib.parse import urlsplit
from flask import Flask, render_template, abort, request, redirect, url_for, flash, session, g
from werkzeug.security import generate_password_hash, check_password_hash
from db import get_db, init_db

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-me")

init_db()  # create tables + sample data on startup if needed

USERNAME_RE = re.compile(r"[A-Za-z0-9_]{3,20}")
MAX_REVIEW_LENGTH = 1000


def safe_next(target):
    """Return target if it's a path on this site, otherwise None (blocks open redirects)."""
    if not target:
        return None
    if any(c.isspace() or ord(c) < 32 for c in target):
        return None
    target_slashes = target.replace("\\", "/")  # browsers treat \ like /
    parts = urlsplit(target_slashes)
    if parts.scheme or parts.netloc or not target_slashes.startswith("/") or target_slashes.startswith("//"):
        return None
    return target


def current_path():
    return request.full_path if request.query_string else request.path


def login_required(view):
    """Send logged-out visitors to the login page, then back here afterwards."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        if g.user is None:
            flash("Please log in first.")
            # After a form POST, come back to the form page itself
            next_url = current_path() if request.method == "GET" else request.path
            return redirect(url_for("login", next=next_url))
        return view(*args, **kwargs)
    return wrapped


@app.before_request
def load_user():
    # Look the user up on every request, so a deleted account (e.g. after resetting
    # the database) is logged out instead of causing errors later.
    g.user = None
    if "user_id" in session:
        conn = get_db()
        g.user = conn.execute("SELECT id, username FROM users WHERE id = ?",
                              (session["user_id"],)).fetchone()
        conn.close()
        if g.user is None:
            session.clear()


@app.context_processor
def inject_user():
    # Makes current_user available in every template (None when logged out)
    return {"current_user": getattr(g, "user", None)}


def log_in(user):
    session.clear()
    session["user_id"] = user["id"]
    session["username"] = user["username"]


@app.route("/")
def index():
    conn = get_db()
    places = conn.execute("""
        SELECT p.id, p.name, p.category, p.location,
               ROUND(AVG(r.rating), 1) AS avg_rating,
               COUNT(r.id) AS num_reviews
        FROM places p
        LEFT JOIN reviews r ON r.place_id = p.id
        GROUP BY p.id
        ORDER BY avg_rating IS NULL, avg_rating DESC, num_reviews DESC
    """).fetchall()
    conn.close()
    return render_template("index.html", places=places)


@app.route("/place/<int:place_id>")
def place(place_id):
    conn = get_db()
    place = conn.execute("SELECT * FROM places WHERE id = ?", (place_id,)).fetchone()
    if place is None:
        conn.close()
        abort(404)  # place doesn't exist

    reviews = conn.execute("""
        SELECT r.rating, r.text, r.created_at, r.user_id, u.username
        FROM reviews r
        JOIN users u ON u.id = r.user_id
        WHERE r.place_id = ?
        ORDER BY r.created_at DESC
    """, (place_id,)).fetchall()
    conn.close()

    # How many 1-star, 2-star ... 5-star reviews, for the chart
    counts = [0, 0, 0, 0, 0]
    for r in reviews:
        counts[r["rating"] - 1] += 1

    avg = round(sum(r["rating"] for r in reviews) / len(reviews), 1) if reviews else None
    reviewed = g.user is not None and any(r["user_id"] == g.user["id"] for r in reviews)

    return render_template("place.html", place=place, reviews=reviews,
                           counts=counts, avg=avg, reviewed=reviewed)


@app.route("/place/<int:place_id>/review", methods=["GET", "POST"])
@login_required
def review(place_id):
    conn = get_db()
    place = conn.execute("SELECT * FROM places WHERE id = ?", (place_id,)).fetchone()
    if place is None:
        conn.close()
        abort(404)

    # Each user gets one review per place, so this decides add vs. edit
    existing = conn.execute(
        "SELECT rating, text FROM reviews WHERE user_id = ? AND place_id = ?",
        (g.user["id"], place_id),
    ).fetchone()

    rating = existing["rating"] if existing else None
    text = existing["text"] if existing else ""

    if request.method == "POST":
        text = request.form.get("text", "").strip()
        try:
            rating = int(request.form.get("rating", ""))
        except ValueError:
            rating = None

        errors = []
        if rating not in (1, 2, 3, 4, 5):
            errors.append("Pick a rating from 1 to 5 stars.")
            rating = None
        if not text:
            errors.append("Write a few words about the place.")
        elif len(text) > MAX_REVIEW_LENGTH:
            errors.append(f"Keep your review to {MAX_REVIEW_LENGTH} characters or fewer "
                          f"(yours is {len(text)}).")

        if errors:
            for e in errors:
                flash(e)
        else:
            # ON CONFLICT covers a double submit from two tabs: it updates instead of crashing
            conn.execute("""
                INSERT INTO reviews (user_id, place_id, rating, text) VALUES (?, ?, ?, ?)
                ON CONFLICT (user_id, place_id)
                DO UPDATE SET rating = excluded.rating, text = excluded.text
            """, (g.user["id"], place_id, rating, text))
            conn.commit()
            conn.close()
            flash("Your review was updated." if existing else "Thanks for your review!")
            return redirect(url_for("place", place_id=place_id))

    conn.close()
    return render_template("review.html", place=place, rating=rating, text=text,
                           editing=existing is not None, max_length=MAX_REVIEW_LENGTH)


@app.route("/register", methods=["GET", "POST"])
def register():
    next_url = safe_next(request.values.get("next"))
    username = ""
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm", "")

        errors = []
        if not username:
            errors.append("Enter a username.")
        elif not USERNAME_RE.fullmatch(username):
            errors.append("Username must be 3–20 characters: letters, numbers, or underscores.")
        if len(password) < 6:
            errors.append("Password must be at least 6 characters.")
        elif password != confirm:
            errors.append("Passwords don't match.")

        if not errors:
            conn = get_db()
            taken = conn.execute("SELECT 1 FROM users WHERE username = ? COLLATE NOCASE",
                                 (username,)).fetchone()
            if taken:
                errors.append("That username is already taken.")
            else:
                try:
                    cur = conn.execute(
                        "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                        (username, generate_password_hash(password, method="pbkdf2:sha256")),
                    )
                    conn.commit()
                except sqlite3.IntegrityError:  # someone grabbed it at the same moment
                    errors.append("That username is already taken.")
            conn.close()

        if errors:
            for e in errors:
                flash(e)
        else:
            # Log the new user straight in
            log_in({"id": cur.lastrowid, "username": username})
            flash(f"Welcome, {username}! Your account is ready.")
            return redirect(next_url or url_for("index"))

    return render_template("register.html", username=username, next=next_url)


@app.route("/login", methods=["GET", "POST"])
def login():
    next_url = safe_next(request.values.get("next"))
    username = ""
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        user = None
        if username and password:
            conn = get_db()
            # Usernames are unique ignoring case (see register), so "Alex" finds alex
            user = conn.execute("SELECT * FROM users WHERE username = ? COLLATE NOCASE",
                                (username,)).fetchone()
            conn.close()

        if not username or not password:
            flash("Enter your username and password.")
        elif user is None or not check_password_hash(user["password_hash"], password):
            flash("Invalid username or password")
        else:
            log_in(user)
            flash(f"Hi, {user['username']}! You're logged in.")
            return redirect(next_url or url_for("index"))

    return render_template("login.html", username=username, next=next_url)


@app.route("/logout")
def logout():
    session.clear()
    flash("You've been logged out.")
    return redirect(url_for("index"))


@app.errorhandler(404)
def not_found(e):
    return render_template("error.html", title="Page not found",
                           message="That page or place doesn't exist."), 404


@app.errorhandler(405)
def method_not_allowed(e):
    return render_template("error.html", title="Not allowed",
                           message="That page can't be used that way."), 405


@app.errorhandler(500)
def server_error(e):
    return render_template("error.html", title="Something went wrong",
                           message="Something went wrong on our end. Please try again."), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    app.run(host="0.0.0.0", port=port, debug=True)
