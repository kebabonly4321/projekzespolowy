from flask import Flask, render_template

app = Flask(__name__)
app.secret_key = "silownia"

@app.route("/", methods=["GET", "POST"])
def login():
    return render_template("logowanie.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    return render_template("rejestracja.html")

if __name__ == '__main__':
    app.run()