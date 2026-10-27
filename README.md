# Rate the Food

Rate the Food ranks places to eat near Santa Clara University. Anyone can browse the
ranking and open a place to see its average rating, a chart of how its ratings break
down, and every review. Users can register, log in, and leave one review per place,
which they can edit later.

Live site: https://food-ratings-307659313428.us-west1.run.app

## About the data

The places are real restaurants near campus. The users and reviews are **sample data**
created when the app first starts, so the rankings don't reflect real opinions yet.

Sample users: `alex`, `jordan`, `sam`, `priya`, `mateo`, `lin`. All of them use the
password `password123`.

## Run it on your laptop

You need Python 3.9 or newer.

```bash
git clone <this repo's URL>
cd food-ratings-HW5
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Then open http://localhost:5001.

The first run creates `food.db` (a SQLite database) and fills it with the sample data.
To start over with fresh sample data, stop the app, delete `food.db`, and run it again.

## Files

| File | What it does |
| --- | --- |
| `app.py` | The Flask app: all routes (home ranking, place page, write/edit review, register, log in, log out), the `login_required` decorator, and the error pages. |
| `db.py` | Database setup: the table schema (`users`, `places`, `reviews`), `get_db()` for opening a connection, and the sample data. |
| `templates/base.html` | Shared layout, navigation bar, flash messages, and all the CSS. |
| `templates/index.html` | Home page: places ranked by average rating. |
| `templates/place.html` | One place: average rating, ratings chart (Chart.js), and reviews. |
| `templates/review.html` | Form to write or edit your review of a place. |
| `templates/login.html`, `templates/register.html` | Log in and sign up forms. |
| `templates/error.html` | Friendly "page not found" and "something went wrong" pages. |
| `requirements.txt` | Python packages to install. |

## Settings

These environment variables are optional when running locally:

- `PORT`: port to run on (default `5001`).
- `SECRET_KEY`: key used to sign login sessions. Set a long random value when deploying.
- `DB_PATH`: where to store the database (default `food.db`).
