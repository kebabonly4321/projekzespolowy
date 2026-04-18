import os
import sqlite3

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


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(error=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        haslo = request.form.get("haslo", "")

        db = get_db()
        user = db.execute(
            "SELECT id, username, password, waga, wzrost FROM users WHERE username = ?",
            (email,),
        ).fetchone()

        if user and check_password_hash(user["password"], haslo):
            session.clear()
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            flash("Pomyślne logowanie.", "error")
            #return redirect(url_for("dashboard"))

        else:
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

        db = get_db()
        existing_user = db.execute(
            "SELECT id FROM users WHERE username = ?",
            (email,),
        ).fetchone()

        if existing_user:
            flash("Użytkownik z takim adresem e-mail już istnieje.", "error")
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

        password_hash = generate_password_hash(haslo)

        db.execute(
            "INSERT INTO users (username, password, waga, wzrost) VALUES (?, ?, ?, ?)",
            (email, password_hash, waga, wzrost),
        )
        db.commit()

        flash("Konto zostało utworzone. Teraz możesz się zalogować.", "success")
        return redirect(url_for("login"))

    return render_template("rejestracja.html")

@app.route("/homepage", methods=["GET", "POST"])
def homepage():
    return render_template("homepage.html")

@app.route("/historia", methods=["GET", "POST"])
def historia():
    return render_template("historia.html")

@app.route("/cwiczenia", methods=["GET", "POST"])
def cwiczenia():
    return render_template("cwiczenia.html")

@app.route("/trening", methods=["GET", "POST"])
def dodaj_trening():
    return render_template("dodajtrening.html")

if __name__ == "__main__":
    app.run(debug=True)