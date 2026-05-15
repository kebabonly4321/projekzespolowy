import os
import sqlite3
from datetime import date, datetime
from functools import wraps

from flask import (
    Flask,
    flash,
    g,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-only-change-me")

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
app.config["DATABASE"] = os.path.join(BASE_DIR, "gym.db")
app.config["SCHEMA"] = os.path.join(BASE_DIR, "database", "schemat.sql")


def normalize_sql_date(value):
    """Zwraca datę jako tekst YYYY-MM-DD do zapisu w SQLite."""
    if not value:
        return datetime.now().strftime("%Y-%m-%d")

    if hasattr(value, "strftime"):
        return value.strftime("%Y-%m-%d")

    value = str(value).strip()
    for pattern in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%d.%m.%Y"):
        try:
            return datetime.strptime(value, pattern).strftime("%Y-%m-%d")
        except ValueError:
            pass

    return value


def parse_sql_date(value):
    """
    Zwraca obiekt date dla template'ów.
    Dzięki temu w HTML może zostać:
        trening.date.strftime('%Y-%m-%d')
    i nie pojawi się błąd: 'str object' has no attribute 'strftime'.
    """
    if not value:
        return datetime.now().date()

    if hasattr(value, "strftime"):
        if isinstance(value, datetime):
            return value.date()
        return value

    value = str(value).strip()
    for pattern in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%d.%m.%Y"):
        try:
            return datetime.strptime(value, pattern).date()
        except ValueError:
            pass

    return datetime.now().date()

MUSCLE_IMAGE_FILES = {
    "klatka piersiowa": "klatka_piersiowa.png",
    "plecy": "plecy.png",
    "nogi": "nogi.png",
    "barki": "barki.png",
    "biceps": "biceps.png",
    "triceps": "triceps.png",
}


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(error=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def ensure_database_exists():
    """Tworzy tabele i podstawowy katalog ćwiczeń, jeżeli baza jest pusta."""
    os.makedirs(os.path.dirname(app.config["DATABASE"]), exist_ok=True)
    with sqlite3.connect(app.config["DATABASE"]) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        table = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='users'"
        ).fetchone()

        if table is None:
            with open(app.config["SCHEMA"], "r", encoding="utf-8") as f:
                conn.executescript(f.read())

        group_count = conn.execute("SELECT COUNT(*) FROM grupa_miesniowa").fetchone()[0]
        if group_count == 0:
            for group_name in MUSCLE_IMAGE_FILES.keys():
                conn.execute(
                    "INSERT INTO grupa_miesniowa (name) VALUES (?)",
                    (group_name,),
                )

        exercise_count = conn.execute("SELECT COUNT(*) FROM cwiczenia").fetchone()[0]
        if exercise_count == 0:
            default_exercises = [
                ("bench press", "klatka piersiowa"),
                ("deadlift", "plecy"),
                ("squat", "nogi"),
                ("shoulder press", "barki"),
                ("barbell curl", "biceps"),
                ("triceps pushdown", "triceps"),
            ]
            for exercise_name, group_name in default_exercises:
                group_id = conn.execute(
                    "SELECT id FROM grupa_miesniowa WHERE name = ?",
                    (group_name,),
                ).fetchone()[0]
                conn.execute(
                    "INSERT INTO cwiczenia (name, muscle_group_id) VALUES (?, ?)",
                    (exercise_name, group_id),
                )

        conn.commit()


def login_required(view_func):
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            flash("Najpierw się zaloguj.", "error")
            return redirect(url_for("login"))
        return view_func(*args, **kwargs)

    return wrapper


def muscle_group_image_url(muscle_group_name):
    if not muscle_group_name:
        return None

    filename = MUSCLE_IMAGE_FILES.get(muscle_group_name.strip().lower())
    if filename is None:
        return None

    return url_for("static", filename=f"images/{filename}")


def get_user_workout_count(user_id):
    db = get_db()
    row = db.execute(
        "SELECT COUNT(*) AS count FROM treningi WHERE user_id = ?",
        (user_id,),
    ).fetchone()
    return row["count"]


def get_last_trainings(user_id, limit=3):
    db = get_db()
    rows = db.execute(
        """
        SELECT
            t.id,
            t.data,
            t.trwanie_treningu,
            t.spalone_kalorie,
            COUNT(cnt.id) AS exercise_count
        FROM treningi AS t
        LEFT JOIN cwiczenia_na_treningu AS cnt
            ON cnt.workout_id = t.id
        WHERE t.user_id = ?
        GROUP BY t.id
        ORDER BY date(t.data) DESC, t.id DESC
        LIMIT ?
        """,
        (user_id, limit),
    ).fetchall()

    return [
        {
            "id": row["id"],
            "name": f"Trening #{row['id']}",
            "date": parse_sql_date(row["data"]),
            "duration": row["trwanie_treningu"],
            "calories": row["spalone_kalorie"],
            "exercise_count": row["exercise_count"],
        }
        for row in rows
    ]


def get_user_trainings(user_id):
    db = get_db()
    rows = db.execute(
        """
        SELECT
            t.id,
            t.data,
            t.trwanie_treningu,
            t.spalone_kalorie,
            COUNT(cnt.id) AS exercise_count
        FROM treningi AS t
        LEFT JOIN cwiczenia_na_treningu AS cnt
            ON cnt.workout_id = t.id
        WHERE t.user_id = ?
        GROUP BY t.id
        ORDER BY date(t.data) DESC, t.id DESC
        """,
        (user_id,),
    ).fetchall()

    trainings = []
    for row in rows:
        training = dict(row)
        training["data"] = parse_sql_date(training["data"])
        trainings.append(training)

    return trainings


def get_exercise_catalog():
    db = get_db()
    rows = db.execute(
        """
        SELECT
            c.id,
            c.name,
            gm.name AS muscle_group_name
        FROM cwiczenia AS c
        JOIN grupa_miesniowa AS gm
            ON gm.id = c.muscle_group_id
        ORDER BY gm.name, c.name
        """
    ).fetchall()

    return [dict(row) for row in rows]


def get_last_exercise(user_id):
    db = get_db()
    row = db.execute(
        """
        SELECT
            cnt.id AS workout_exercise_id,
            cnt.rep_count,
            cnt.weight,
            c.id AS exercise_id,
            c.name AS exercise_name,
            gm.name AS muscle_group_name,
            t.id AS workout_id,
            t.data AS workout_date
        FROM cwiczenia_na_treningu AS cnt
        JOIN treningi AS t
            ON t.id = cnt.workout_id
        JOIN cwiczenia AS c
            ON c.id = cnt.exercise_id
        JOIN grupa_miesniowa AS gm
            ON gm.id = c.muscle_group_id
        WHERE t.user_id = ?
        ORDER BY cnt.id DESC
        LIMIT 1
        """,
        (user_id,),
    ).fetchone()

    if row is None:
        return None

    return {
        "id": row["workout_exercise_id"],
        "name": row["exercise_name"],
        "exercise_id": row["exercise_id"],
        "workout_id": row["workout_id"],
        "workout_date": parse_sql_date(row["workout_date"]),
        "rep_count": row["rep_count"],
        "weight": row["weight"],
        "muscle_group_name": row["muscle_group_name"],
        "image_url": muscle_group_image_url(row["muscle_group_name"]),
    }


@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        haslo = request.form.get("haslo", "")

        if not email or not haslo:
            flash("Uzupełnij adres e-mail i hasło.", "error")
            return render_template("logowanie.html")

        db = get_db()
        user = db.execute(
            "SELECT id, username, password, waga, wzrost FROM users WHERE username = ?",
            (email,),
        ).fetchone()

        password_ok = False
        if user:
            password_hash = user["password"]
            password_ok = check_password_hash(password_hash, haslo)
            if not password_ok and password_hash == haslo:
                password_ok = True
                db.execute(
                    "UPDATE users SET password = ? WHERE id = ?",
                    (generate_password_hash(haslo), user["id"]),
                )
                db.commit()

        if user and password_ok:
            session.clear()
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            flash("Pomyślne logowanie.", "success")
            return redirect(url_for("homepage"))

        flash("Nieprawidłowy adres e-mail lub hasło.", "error")

    return render_template("logowanie.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        haslo = request.form.get("haslo", "")
        haslo_rep = request.form.get("haslo_rep", "")
        waga_raw = request.form.get("waga", "").strip().replace(",", ".")
        wzrost_raw = request.form.get("wzrost", "").strip().replace(",", ".")

        if not email or not haslo or not haslo_rep or not waga_raw or not wzrost_raw:
            flash("Wypełnij wszystkie pola.", "error")
            return render_template("rejestracja.html")

        if haslo != haslo_rep:
            flash("Hasła nie są takie same.", "error")
            return render_template("rejestracja.html")

        try:
            waga = float(waga_raw)
            wzrost = float(wzrost_raw)
        except ValueError:
            flash("Waga i wzrost muszą być liczbami.", "error")
            return render_template("rejestracja.html")

        if waga <= 0 or wzrost <= 0:
            flash("Waga i wzrost muszą być większe od zera.", "error")
            return render_template("rejestracja.html")

        db = get_db()
        existing_user = db.execute(
            "SELECT id FROM users WHERE username = ?",
            (email,),
        ).fetchone()

        if existing_user:
            flash("Użytkownik z takim adresem e-mail już istnieje.", "error")
            return render_template("rejestracja.html")

        db.execute(
            "INSERT INTO users (username, password, waga, wzrost) VALUES (?, ?, ?, ?)",
            (email, generate_password_hash(haslo), waga, wzrost),
        )
        db.commit()

        flash("Konto zostało utworzone. Teraz możesz się zalogować.", "success")
        return redirect(url_for("login"))

    return render_template("rejestracja.html")


@app.route("/homepage")
@login_required
def homepage():
    user_id = session["user_id"]
    workout_count = get_user_workout_count(user_id)

    context = {
        "username": session.get("username"),
        "last_trainings": get_last_trainings(user_id),
        "has_any_training": workout_count > 0,
        "last_exercise": get_last_exercise(user_id),
    }
    return render_template("homepage.html", **context)


@app.route("/historia")
@login_required
def historia():
    return render_template(
        "historia.html",
        trainings=get_user_trainings(session["user_id"]),
    )


@app.route("/cwiczenia", methods=["GET", "POST"])
@login_required
def cwiczenia():
    user_id = session["user_id"]
    db = get_db()

    if request.method == "POST":
        workout_id = request.form.get("workout_id", type=int)
        exercise_id = request.form.get("exercise_id", type=int)
        rep_count = request.form.get("rep_count", type=int)
        weight_raw = request.form.get("weight", "").strip().replace(",", ".")

        if not workout_id or not exercise_id:
            flash("Wybierz trening i ćwiczenie.", "error")
            return redirect(url_for("cwiczenia"))

        workout = db.execute(
            "SELECT id FROM treningi WHERE id = ? AND user_id = ?",
            (workout_id, user_id),
        ).fetchone()
        if workout is None:
            flash("Wybrany trening nie należy do zalogowanego użytkownika.", "error")
            return redirect(url_for("cwiczenia"))

        exercise = db.execute(
            "SELECT id FROM cwiczenia WHERE id = ?",
            (exercise_id,),
        ).fetchone()
        if exercise is None:
            flash("Nie znaleziono wybranego ćwiczenia.", "error")
            return redirect(url_for("cwiczenia"))

        try:
            weight = float(weight_raw) if weight_raw else None
        except ValueError:
            flash("Ciężar musi być liczbą.", "error")
            return redirect(url_for("cwiczenia"))

        if rep_count is not None and rep_count <= 0:
            flash("Liczba powtórzeń musi być większa od zera.", "error")
            return redirect(url_for("cwiczenia"))

        if weight is not None and weight < 0:
            flash("Ciężar nie może być ujemny.", "error")
            return redirect(url_for("cwiczenia"))

        db.execute(
            """
            INSERT INTO cwiczenia_na_treningu
                (workout_id, exercise_id, rep_count, weight)
            VALUES (?, ?, ?, ?)
            """,
            (workout_id, exercise_id, rep_count, weight),
        )
        db.commit()

        flash("Ćwiczenie zostało dodane do wybranego treningu.", "success")
        return redirect(url_for("homepage"))

    return render_template(
        "cwiczenia.html",
        exercises=get_exercise_catalog(),
        trainings=get_user_trainings(user_id),
    )


@app.route("/trening", methods=["GET", "POST"])
@login_required
def dodaj_trening():
    if request.method == "POST":
        data = normalize_sql_date(request.form.get("data"))
        trwanie_treningu = request.form.get("trwanie_treningu", type=int)
        spalone_kalorie = request.form.get("spalone_kalorie", type=int)

        if trwanie_treningu is not None and trwanie_treningu <= 0:
            flash("Czas trwania treningu musi być większy od zera.", "error")
            return redirect(url_for("dodaj_trening"))

        db = get_db()

        db.execute(
            """
            INSERT INTO treningi
                (user_id, data, trwanie_treningu, spalone_kalorie)
            VALUES (?, ?, ?, ?)
            """,
            (session["user_id"], data, trwanie_treningu, spalone_kalorie),
        )
        db.commit()

        flash("Trening został utworzony. Możesz teraz dodać do niego ćwiczenia.", "success")
        return redirect(url_for("cwiczenia"))

    return render_template("dodajtrening.html", today=datetime.now().strftime("%Y-%m-%d"))


@app.route("/profil")
@login_required
def profil():
    db = get_db()
    user = db.execute(
        "SELECT username, waga, wzrost FROM users WHERE id = ?",
        (session["user_id"],),
    ).fetchone()
    return render_template("profil.html", user=user)


@app.route("/logout")
@login_required
def logout():
    session.clear()
    flash("Zostałeś wylogowany.", "success")
    return redirect(url_for("login"))

@app.route("/zmiana_hasla")
def zmiana_hasla():
    return redirect(url_for("profil"))

@app.route("/edytuj_profil")
def edytuj_profil():
    return redirect(url_for("profil"))

ensure_database_exists()

if __name__ == "__main__":
    app.run(debug=True)
