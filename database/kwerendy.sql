-- lista użytkowników
SELECT id, username, waga, wzrost FROM users;

-- lista treningów
SELECT * FROM treningi;

-- ćwiczenia z grupą mięśniową
SELECT
    cwiczenia.name AS cwiczenie,
    grupa_miesniowa.name AS grupa_miesniowa
FROM cwiczenia
JOIN grupa_miesniowa
ON cwiczenia.muscle_group_id = grupa_miesniowa.id;

-- szczegóły treningu
SELECT
    treningi.id AS trening,
    cwiczenia.name AS cwiczenie,
    cwiczenia_na_treningu.rep_count,
    cwiczenia_na_treningu.weight
FROM cwiczenia_na_treningu
JOIN cwiczenia ON cwiczenia_na_treningu.exercise_id = cwiczenia.id
JOIN treningi ON cwiczenia_na_treningu.workout_id = treningi.id;

-- historia treningów użytkownika
SELECT
    users.username,
    treningi.data,
    treningi.trwanie_treningu,
    treningi.spalone_kalorie
FROM treningi
JOIN users ON treningi.user_id = users.id;