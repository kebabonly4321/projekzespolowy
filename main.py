import os
import re
import sqlite3
from datetime import datetime
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
app.config["EXERCISES"] = os.path.join(BASE_DIR, "database", "przykladowe_cwiczenia.sql")


def normalize_sql_date(value):
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


BADGE_LEVELS = [
    {
        "key": "bronze",
        "name": "Brązowa odznaka",
        "threshold": 5000,
        "image": "odznaka_bronze.png",
    },
    {
        "key": "silver",
        "name": "Srebrna odznaka",
        "threshold": 10000,
        "image": "odznaka_silver.png",
    },
    {
        "key": "gold",
        "name": "Złota odznaka",
        "threshold": 20000,
        "image": "odznaka_gold.png",
    },
    {
        "key": "red",
        "name": "Czerwona odznaka",
        "threshold": 40000,
        "image": "odznaka_red.png",
    },
]


def format_kg(value):
    value = float(value or 0)
    if value.is_integer():
        return str(int(value))
    return f"{value:.1f}".replace(".", ",")


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
            cnt.id AS workout_exercise_id,
            cnt.rep_count,
            cnt.weight,
            c.name AS exercise_name,
            gm.name AS muscle_group_name
        FROM treningi AS t
        LEFT JOIN cwiczenia_na_treningu AS cnt
            ON cnt.workout_id = t.id
        LEFT JOIN cwiczenia AS c
            ON c.id = cnt.exercise_id
        LEFT JOIN grupa_miesniowa AS gm
            ON gm.id = c.muscle_group_id
        WHERE t.user_id = ?
        ORDER BY date(t.data) DESC, t.id DESC, cnt.id ASC
        """,
        (user_id,),
    ).fetchall()

    trainings_by_id = {}
    for row in rows:
        training_id = row["id"]
        if training_id not in trainings_by_id:
            trainings_by_id[training_id] = {
                "id": training_id,
                "data": parse_sql_date(row["data"]),
                "trwanie_treningu": row["trwanie_treningu"],
                "spalone_kalorie": row["spalone_kalorie"],
                "exercises": [],
                "muscle_groups": [],
                "_muscle_group_names": set(),
            }

        if row["workout_exercise_id"] is not None:
            muscle_group_name = row["muscle_group_name"]
            image_url = muscle_group_image_url(muscle_group_name)

            trainings_by_id[training_id]["exercises"].append(
                {
                    "name": row["exercise_name"],
                    "muscle_group_name": muscle_group_name,
                    "muscle_group_image_url": image_url,
                    "rep_count": row["rep_count"],
                    "weight": row["weight"],
                }
            )

            if muscle_group_name:
                normalized_group_name = muscle_group_name.strip().lower()
                if normalized_group_name not in trainings_by_id[training_id]["_muscle_group_names"]:
                    trainings_by_id[training_id]["_muscle_group_names"].add(normalized_group_name)
                    trainings_by_id[training_id]["muscle_groups"].append(
                        {
                            "name": muscle_group_name,
                            "image_url": image_url,
                        }
                    )

    trainings = list(trainings_by_id.values())
    for training in trainings:
        training["exercise_count"] = len(training["exercises"])
        training.pop("_muscle_group_names", None)

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



def badge_image_url(image_filename):
    return url_for("static", filename=f"images/{image_filename}")


def make_badge(muscle_group_name, points, level, earned_on=None):
    return {
        "key": level["key"],
        "name": level["name"],
        "threshold": level["threshold"],
        "threshold_label": format_kg(level["threshold"]),
        "muscle_group_name": muscle_group_name,
        "points": float(points or 0),
        "points_label": format_kg(points),
        "image_url": badge_image_url(level["image"]),
        "earned_on": earned_on,
        "title": f"{level['name']} — {muscle_group_name}",
    }


def get_user_muscle_group_points(user_id):
    #Liczy kilogramy przeniesione przez użytkownika osobno dla każdej partii ciała.
    db = get_db()
    rows = db.execute(
        """
        SELECT
            gm.name AS muscle_group_name,
            COALESCE(SUM(COALESCE(cnt.rep_count, 0) * COALESCE(cnt.weight, 0)), 0) AS points
        FROM treningi AS t
        JOIN cwiczenia_na_treningu AS cnt
            ON cnt.workout_id = t.id
        JOIN cwiczenia AS c
            ON c.id = cnt.exercise_id
        JOIN grupa_miesniowa AS gm
            ON gm.id = c.muscle_group_id
        WHERE t.user_id = ?
        GROUP BY gm.id, gm.name
        ORDER BY gm.name
        """,
        (user_id,),
    ).fetchall()

    return [
        {
            "muscle_group_name": row["muscle_group_name"],
            "points": float(row["points"] or 0),
            "points_label": format_kg(row["points"]),
        }
        for row in rows
    ]


def get_user_badges(user_id):
    #Zwraca wszystkie odznaki zdobyte przez użytkownika dla poszczególnych partii ciała.
    badges = []
    for group_points in get_user_muscle_group_points(user_id):
        points = group_points["points"]
        for level in BADGE_LEVELS:
            if points >= level["threshold"]:
                badges.append(
                    make_badge(
                        group_points["muscle_group_name"],
                        points,
                        level,
                    )
                )

    badges.sort(
        key=lambda badge: (
            badge["muscle_group_name"].lower(),
            badge["threshold"],
        )
    )
    return badges


def get_last_badge(user_id):
    #Zwraca ostatnią zdobytą odznakę.
    db = get_db()
    rows = db.execute(
        """
        SELECT
            t.id AS workout_id,
            t.data AS workout_date,
            cnt.id AS workout_exercise_id,
            COALESCE(cnt.rep_count, 0) AS rep_count,
            COALESCE(cnt.weight, 0) AS weight,
            gm.name AS muscle_group_name
        FROM cwiczenia_na_treningu AS cnt
        JOIN treningi AS t
            ON t.id = cnt.workout_id
        JOIN cwiczenia AS c
            ON c.id = cnt.exercise_id
        JOIN grupa_miesniowa AS gm
            ON gm.id = c.muscle_group_id
        WHERE t.user_id = ?
        ORDER BY t.id ASC, cnt.id ASC
        """,
        (user_id,),
    ).fetchall()

    totals_by_group = {}
    last_badge = None

    for row in rows:
        muscle_group = row["muscle_group_name"]
        previous_points = totals_by_group.get(muscle_group, 0.0)
        moved_points = float(row["rep_count"] or 0) * float(row["weight"] or 0)
        current_points = previous_points + moved_points
        totals_by_group[muscle_group] = current_points

        for level in BADGE_LEVELS:
            if previous_points < level["threshold"] <= current_points:
                last_badge = make_badge(
                    muscle_group,
                    current_points,
                    level,
                    parse_sql_date(row["workout_date"]),
                )

    return last_badge


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
        "last_badge": get_last_badge(user_id),
    }
    return render_template("homepage.html", **context)


@app.route("/historia")
@login_required
def historia():
    return render_template(
        "historia.html",
        trainings=get_user_trainings(session["user_id"]),
    )


@app.route("/cwiczenia")
@login_required
def cwiczenia():
    return render_template(
        "cwiczenia.html",
        exercises=get_exercise_catalog(),
    )


@app.route("/trening", methods=["GET", "POST"])
@login_required
def dodaj_trening():
    db = get_db()

    if request.method == "POST":
        data = normalize_sql_date(request.form.get("data"))
        trwanie_treningu = request.form.get("trwanie_treningu", type=int)
        spalone_kalorie = request.form.get("spalone_kalorie", type=int)
        exercise_ids = request.form.getlist("exercise_id")
        rep_counts = request.form.getlist("rep_count")
        weights_raw = request.form.getlist("weight")

        if trwanie_treningu is not None and trwanie_treningu <= 0:
            flash("Czas trwania treningu musi być większy od zera.", "error")
            return redirect(url_for("dodaj_trening"))

        selected_exercises = []
        for index, exercise_id_raw in enumerate(exercise_ids):
            if not exercise_id_raw:
                continue

            try:
                exercise_id = int(exercise_id_raw)
            except ValueError:
                flash("Wybrano nieprawidłowe ćwiczenie.", "error")
                return redirect(url_for("dodaj_trening"))

            rep_count = None
            if index < len(rep_counts) and rep_counts[index].strip():
                try:
                    rep_count = int(rep_counts[index])
                except ValueError:
                    flash("Liczba powtórzeń musi być liczbą całkowitą.", "error")
                    return redirect(url_for("dodaj_trening"))

                if rep_count <= 0:
                    flash("Liczba powtórzeń musi być większa od zera.", "error")
                    return redirect(url_for("dodaj_trening"))

            weight = None
            if index < len(weights_raw) and weights_raw[index].strip():
                try:
                    weight = float(weights_raw[index].strip().replace(",", "."))
                except ValueError:
                    flash("Ciężar musi być liczbą.", "error")
                    return redirect(url_for("dodaj_trening"))

                if weight < 0:
                    flash("Ciężar nie może być ujemny.", "error")
                    return redirect(url_for("dodaj_trening"))

            exercise = db.execute(
                "SELECT id FROM cwiczenia WHERE id = ?",
                (exercise_id,),
            ).fetchone()
            if exercise is None:
                flash("Nie znaleziono wybranego ćwiczenia.", "error")
                return redirect(url_for("dodaj_trening"))

            selected_exercises.append((exercise_id, rep_count, weight))

        if not selected_exercises:
            flash("Dodaj co najmniej jedno ćwiczenie do treningu.", "error")
            return redirect(url_for("dodaj_trening"))

        cursor = db.execute(
            """
            INSERT INTO treningi
                (user_id, data, trwanie_treningu, spalone_kalorie)
            VALUES (?, ?, ?, ?)
            """,
            (session["user_id"], data, trwanie_treningu, spalone_kalorie),
        )
        workout_id = cursor.lastrowid

        db.executemany(
            """
            INSERT INTO cwiczenia_na_treningu
                (workout_id, exercise_id, rep_count, weight)
            VALUES (?, ?, ?, ?)
            """,
            [
                (workout_id, exercise_id, rep_count, weight)
                for exercise_id, rep_count, weight in selected_exercises
            ],
        )
        db.commit()

        flash("Trening wraz z ćwiczeniami został utworzony.", "success")
        return redirect(url_for("homepage"))

    return render_template(
        "dodajtrening.html",
        today=datetime.now().strftime("%Y-%m-%d"),
        exercises=get_exercise_catalog(),
    )


@app.route("/profil")
@login_required
def profil():
    db = get_db()
    user_id = session["user_id"]
    user = db.execute(
        "SELECT username, waga, wzrost FROM users WHERE id = ?",
        (user_id,),
    ).fetchone()

    return render_template(
        "profil.html",
        user=user,
        badges=get_user_badges(user_id),
        muscle_group_points=get_user_muscle_group_points(user_id),
    )


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


if __name__ == "__main__":
    app.run(debug=True)
