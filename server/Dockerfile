FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /srv

COPY app/requirements.txt ./requirements.txt
RUN pip install -r requirements.txt

RUN groupadd --gid 10001 backend \
    && useradd --uid 10001 --gid backend --no-create-home backend \
    && mkdir -p /srv/covers \
    && chown backend:backend /srv/covers

COPY app ./app
COPY migrations ./migrations
COPY data ./data
COPY alembic.ini ./alembic.ini

USER backend
EXPOSE 8000

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
