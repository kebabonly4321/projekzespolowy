INSERT INTO users (username, password, waga, wzrost)
VALUES ('testuser', 'testh', 80, 180);

INSERT INTO grupa_miesniowa (name) VALUES
('klatka piersiowa'),
('plecy'),
('nogi'),
('barki'),
('biceps'),
('triceps');

INSERT INTO cwiczenia (name, muscle_group_id) VALUES
('bench press', 1),
('deadlift', 2),
('squat', 3),
('shoulder press', 4),
('barbell curl', 5),
('triceps pushdown', 6);

INSERT INTO treningi (user_id, data, trwanie_treningu, spalone_kalorie)
VALUES (1, '2026-01-07', 60, 450);

INSERT INTO cwiczenia_na_treningu (workout_id, exercise_id, rep_count, weight) VALUES
(1, 1, 10, 80),
(1, 1, 8, 85),
(1, 5, 12, 30),
(1, 6, 12, 35);