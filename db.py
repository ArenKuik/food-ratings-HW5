import os
import random
import sqlite3
from werkzeug.security import generate_password_hash

DB_PATH = os.environ.get("DB_PATH", "food.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS places (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    category TEXT NOT NULL,
    location TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id),
    place_id INTEGER NOT NULL REFERENCES places(id),
    rating INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
    text TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (user_id, place_id)
);
"""

# Places near campus: (name, category, location, typical rating for fake reviews)
PLACES = [
    ("The Hut", "Bar & Grill", "Benton St", 3.8),
    ("Hungry Hound", "Burgers", "Benton St", 4.1),
    ("Mio Vicino", "Italian", "Benton St & Monroe St", 4.4),
    ("Toppings Tree", "Filipino", "Franklin St & Jackson St", 4.3),
    ("Pizza My Heart", "Pizza", "Park Ave & The Alameda", 4.0),
    ("Shawarmaji", "Middle Eastern", "The Alameda & El Camino Real", 4.5),
    ("Ramen Taka", "Japanese", "The Alameda", 4.2),
    ("Deedee's", "Indian (vegetarian)", "Washington St", 4.4),
    ("Iraklis Restaurant", "Greek", "El Camino Real & Scott Blvd", 4.0),
    ("Tay Ho", "Vietnamese", "El Camino Real & Scott Blvd", 4.1),
    ("Holder's Mission City Grill", "American", "El Camino Real & Scott Blvd", 3.7),
    ("Chick-fil-A", "Fast food", "El Camino Real & Scott Blvd", 3.9),
    ("Denny's", "Diner", "El Camino Real", 3.2),
    ("Kabab & Curry's", "Indian / Pakistani", "El Camino Real & Pierce St", 4.2),
]

USERS = ["alex", "jordan", "sam", "priya", "mateo", "lin"]

COMMENTS = {
    1: ["Would not go back.", "Cold food and a long wait.", "Really disappointing."],
    2: ["Meh. Only if nothing else is open.", "Overpriced for what you get."],
    3: ["Fine for a quick bite.", "Decent, nothing special.", "OK when you're in a hurry."],
    4: ["Solid choice, I go often.", "Good food, friendly staff.", "Pretty great value."],
    5: ["Best near campus, hands down!", "Amazing, I'm obsessed.", "Never had a bad meal here."],
}


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row          # lets you use row["name"]
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """Create tables, and fill with fake data the first time."""
    conn = get_db()
    conn.executescript(SCHEMA)
    empty = conn.execute("SELECT COUNT(*) FROM places").fetchone()[0] == 0
    if empty:
        seed(conn)
    conn.commit()
    conn.close()


def seed(conn):
    rng = random.Random(42)  # same fake data every time

    for name, category, location, _ in PLACES:
        conn.execute(
            "INSERT INTO places (name, category, location) VALUES (?, ?, ?)",
            (name, category, location),
        )

    # Every fake user has the password "password123"
    for username in USERS:
        conn.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                        (username, generate_password_hash("password123", method="pbkdf2:sha256")),
        )

    user_ids = [r["id"] for r in conn.execute("SELECT id FROM users")]
    places = conn.execute("SELECT id, name FROM places").fetchall()
    typical = {name: avg for name, _, _, avg in PLACES}

    for user_id in user_ids:
        for place in rng.sample(places, k=rng.randint(5, 9)):
            rating = round(rng.gauss(typical[place["name"]], 0.8))
            rating = max(1, min(5, rating))
            conn.execute(
                "INSERT INTO reviews (user_id, place_id, rating, text) VALUES (?, ?, ?, ?)",
                (user_id, place["id"], rating, rng.choice(COMMENTS[rating])),
            )