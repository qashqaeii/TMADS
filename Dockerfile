FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ARG DJANGO_SETTINGS_MODULE=config.settings.local
ENV DJANGO_SETTINGS_MODULE=${DJANGO_SETTINGS_MODULE}

RUN python manage.py collectstatic --noinput

RUN useradd --create-home --uid 1000 --shell /usr/sbin/nologin tmads \
    && chown -R tmads:tmads /app

USER tmads

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/accounts/login/', timeout=3)" || exit 1

CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2", "--timeout", "120"]