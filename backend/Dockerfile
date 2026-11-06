FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml ./
COPY app ./app
RUN pip install --no-cache-dir .

COPY data ./data

# The corpus and datasets live in /app/data, the database in the /db volume.
ENV AGENTLAB_DATA_DIR=/app/data \
    AGENTLAB_DATABASE_URL=sqlite:////db/agentlab.db
VOLUME /db

EXPOSE 8000
CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
