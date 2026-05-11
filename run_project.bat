@echo off

cd /d %~dp0

echo ==============================
echo Instalacja bibliotek
 echo ==============================

python -m pip install -r requirements.txt

echo.
echo ==============================
echo Tworzenie bazy danych
 echo ==============================

if exist gym.db del gym.db

sqlite3 gym.db ".read database/schemat.sql"
sqlite3 gym.db ".read database/testdane.sql"
sqlite3 gym.db ".read database/przykladowe_cwiczenia.sql"

echo.
echo ==============================
echo Uruchamianie aplikacji Flask
 echo ==============================

python main.py

pause