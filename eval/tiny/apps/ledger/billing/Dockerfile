FROM python:3.13-slim
WORKDIR /app/billing
COPY ledger-sdk /app/ledger-sdk
COPY billing /app/billing
RUN pip install --no-cache-dir -r requirements.txt
CMD ["gunicorn", "-w", "1", "-b", "0.0.0.0:41411", "wsgi:app"]
