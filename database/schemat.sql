PRAGMA foreign_keys = ON;

CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password TEXT NOT NULL,
    waga REAL,
    wzrost REAL
);

CREATE TABLE grupa_miesniowa (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL
);

CREATE TABLE cwiczenia (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    muscle_group_id INTEGER,
    FOREIGN KEY (muscle_group_id) REFERENCES grupa_miesniowa(id)
);

CREATE TABLE treningi (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    data TEXT,
    trwanie_treningu INTEGER,
    spalone_kalorie INTEGER,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE cwiczenia_na_treningu (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workout_id INTEGER,
    exercise_id INTEGER,
    rep_count INTEGER,
    weight REAL,
    FOREIGN KEY (workout_id) REFERENCES treningi(id),
    FOREIGN KEY (exercise_id) REFERENCES cwiczenia(id)
);