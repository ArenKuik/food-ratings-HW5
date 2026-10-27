import os
import re
import sqlite3
from functools import wraps
from flask import Flask, render_template, abort, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
from db import get_db, init_db

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-me")

init_db()  # create tables + sample data on startup if needed

USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{3,20}$")


def login_required(view):
    """Send logged-out visitors to the login page."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in first.")
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


@app.context_processor
def inject_user():
    # Makes current_user available in every template (None when logged out)
    if "user_id" in session:
        return {"current_user": {"id": session["user_id"], "username": session["username"]}}
    return {"current_user": None}


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
    reviewed = any(r["user_id"] == session.get("user_id") for r in reviews)

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
        (session["user_id"], place_id),
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
        elif len(text) > 1000:
            errors.append("Keep your review under 1000 characters.")

        if errors:
            for e in errors:
                flash(e)
        else:
            if existing:
                conn.execute(
                    "UPDATE reviews SET rating = ?, text = ? WHERE user_id = ? AND place_id = ?",
                    (rating, text, session["user_id"], place_id),
                )
                flash("Your review was updated.")
            else:
                conn.execute(
                    "INSERT INTO reviews (user_id, place_id, rating, text) VALUES (?, ?, ?, ?)",
                    (session["user_id"], place_id, rating, text),
                )
                flash("Thanks for your review!")
            conn.commit()
            conn.close()
            return redirect(url_for("place", place_id=place_id))

    conn.close()
    return render_template("review.html", place=place, rating=rating, text=text,
                           editing=existing is not None)


@app.route("/register", methods=["GET", "POST"])
def register():
    username = ""
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm", "")

        errors = []
        if not USERNAME_RE.match(username):
            errors.append("Username must be 3–20 characters: letters, numbers, or underscores.")
        if len(password) < 6:
            errors.append("Password must be at least 6 characters.")
        if password != confirm:
            errors.append("Passwords don't match.")

        conn = get_db()
        if not errors:
            taken = conn.execute("SELECT 1 FROM users WHERE username = ? COLLATE NOCASE",
                                 (username,)).fetchone()
            if taken:
                errors.append("That username is already taken.")

        if not errors:
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
            session.clear()
            session["user_id"] = cur.lastrowid
            session["username"] = username
            flash(f"Welcome, {username}! Your account is ready.")
            return redirect(url_for("index"))

    return render_template("register.html", username=username)


@app.route("/login", methods=["GET", "POST"])
def login():
    username = ""
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        conn = get_db()
        user = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        conn.close()

        if user is None or not check_password_hash(user["password_hash"], password):
            flash("Invalid username or password")
        else:
            session.clear()
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            flash(f"Hi, {user['username']}! You're logged in.")
            return redirect(url_for("index"))

    return render_template("login.html", username=username)


@app.route("/logout")
def logout():
    session.clear()
    flash("You've been logged out.")
    return redirect(url_for("index"))


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)