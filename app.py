import os
from flask import Flask, render_template
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


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)