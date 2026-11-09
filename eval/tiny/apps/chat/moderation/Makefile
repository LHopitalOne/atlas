PY ?= .venv/bin/python

proto:
	$(PY) -m grpc_tools.protoc -Iapp/pb=protos --python_out=. --grpc_python_out=. protos/moderation.proto

run: proto
	$(PY) -m app.server
