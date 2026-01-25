@echo off
echo === ЗАПУСК БОТА ЦЕННОСТЕЙ ===
echo.

cd /d "C:\Users\dubko\OneDrive\Desktop\ValueGameBot"

echo 1. Установка библиотек...
"C:\Users\dubko\AppData\Local\Python\bin\python.exe" -m pip install aiogram aiohttp python-dotenv --quiet

echo 2. Запуск бота...
echo ===========================
"C:\Users\dubko\AppData\Local\Python\bin\python.exe" bot_new.py

echo.
pause