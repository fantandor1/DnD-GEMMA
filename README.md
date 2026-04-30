# RPG Memory DM

Демо-приложение для текстовой НРИ с ИИ-DM, постоянной памятью мира, листом героя, квестами, локациями, персонажами и игровой сценой 16:9.

## Что внутри

- FastAPI + SQLite.
- Рабочий интерфейс для настройки кампании и памяти мира.
- Игровой fixed-stage интерфейс с PNG-сценой, эмоциями Gemma, d20 и TTS.
- Поддержка локального LM Studio и Google/Gemini API.
- Для публичного демо API-ключи вводятся в браузере и хранятся только в `localStorage`.

## Безопасность ключей

Реальные ключи нельзя коммитить. Локальный `.env` игнорируется через `.gitignore`.

Для демо на Vercel оставь серверные ключи пустыми. Пользователь вводит:

- `Google API key для текста`: рекомендованы Gemma 4 или Gemini 3.1 Pro.
- `Google API key для голоса`: рекомендован Gemini Flash TTS, пресет Leda уже настроен.

## Локальный запуск

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe -m uvicorn rpg_dm.main:app --host 127.0.0.1 --port 8008 --reload
```

Открой `http://127.0.0.1:8008`.

## Vercel

Для Vercel используется облегчённый `requirements.txt`: без `torch` и Silero. Silero остаётся локальной опцией, но не нужен для публичного сайта.

```powershell
npm i -g vercel
vercel login
vercel
```

База данных на Vercel создаётся во временной SQLite в `/tmp`, поэтому демо-данные могут сбрасываться после cold start. Для портфолио-демо этого достаточно; для продакшена лучше подключить постоянную БД.

## GitHub

Перед публикацией проверь, что `.env` не попал в индекс:

```powershell
git status --ignored
git add .
git commit -m "Prepare public RPG Memory DM demo"
git remote add origin https://github.com/<user>/<repo>.git
git push -u origin main
```
