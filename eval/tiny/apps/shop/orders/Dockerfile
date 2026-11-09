FROM python:3.13-slim
WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV ORDERS_HOST=0.0.0.0
CMD ["python", "wsgi.py"]
