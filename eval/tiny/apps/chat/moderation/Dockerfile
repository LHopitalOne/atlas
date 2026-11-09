FROM python:3.13-slim
WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN python -m grpc_tools.protoc -Iapp/pb=protos --python_out=. --grpc_python_out=. protos/moderation.proto
CMD ["python", "-m", "app.server"]
