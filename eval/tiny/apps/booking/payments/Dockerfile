FROM python:3.13-slim
WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
CMD ["gunicorn", "--bind", "0.0.0.0:41820", "--workers", "1", "--threads", "4", "app:create_app()"]
