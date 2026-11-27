# Запуск бэкенда

## Подготовка

Локальный запуск: создание базы PostgreSQL

```sql
CREATE DATABASE spo_diary_db;
```

Файл `.env` из тг размещается в `server/app/.env`. Значения `DB_*` должны соответствовать локальной БД. Для Docker ручное создание базы не требуется.

Окружение для запуска без Docker. Команды из `server`:

```powershell
py -3.12 -m venv app/.venv
app/.venv/Scripts/python.exe -m pip install -r app/requirements.txt
```

## 1. Запуск через PyCharm

- Корень проекта: `проект`.
- Конфигурация: **Бэкенд без Docker** → Run.
- Интерпретатор: `server/app/.venv/Scripts/python.exe`.
- Stop завершает API и обработчик отзывов.

Конфигурация запускает `dev.py`: миграции и импорт `data/works.json` в БД выполняются автоматически перед запуском API и обработчика отзывов.

## 2. Терминал: совместный запуск

Из `server`:

```powershell
app/.venv/Scripts/python.exe dev.py
```

Миграции и импорт `data/works.json` в БД выполняются автоматически. Затем запускаются API и обработчик отзывов. Остановка: `Ctrl+C`.

## 3. Терминал: раздельный запуск

Импорт `data/works.json` в БД, из `server`:

```powershell
app/.venv/Scripts/python.exe data/load.py
```

Скрипт применяет миграции и загружает каталог. Повторный импорт не создаёт дубли. Обложки остаются в `app/covers/catalog`.

Запуск API в том же терминале:

```powershell
app/.venv/Scripts/python.exe -m uvicorn app.main:app --reload
```

Второй терминал, директория `server`:

```powershell
app/.venv/Scripts/python.exe -m app.worker
```

Остановка: `Ctrl+C` в каждом терминале.

## 4. Docker

Docker Desktop. Команды из `server`:

```powershell
docker compose --env-file app/.env up -d --build
```

Compose создаёт отдельную БД, применяет миграции и импортирует `data/works.json`. После импорта запускаются API и обработчик отзывов.

Логи:

```powershell
docker compose --env-file app/.env logs -f api worker
```

Остановка с сохранением данных:

```powershell
docker compose --env-file app/.env down
```

## Подключение фронтенда

API: `http://127.0.0.1:8000/api/v1`. Прокси: `/api` → `http://127.0.0.1:8000`

[Контракт API](API.md).
