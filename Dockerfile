FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Data volume: specs JSON files + SQLite DB
RUN mkdir -p data/specs

ENV DB_PATH=data/forge.db
ENV SPECS_DIR=data/specs

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
