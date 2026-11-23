FROM python:3.12-slim

WORKDIR /app

COPY server.py index.html ./

EXPOSE 8000
ENV HOST=0.0.0.0 PORT=8000 DATA_SOURCES_URL=http://datasources:8001

CMD ["python", "server.py"]
