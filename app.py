import os
from flask import Flask, render_template, abort
from db import get_db, init_db

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-me")

init_db()  # create tables + sample data on startup if needed


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
        SELECT r.rating, r.text, r.created_at, u.username
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

    return render_template("place.html", place=place, reviews=reviews,
                           counts=counts, avg=avg)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)