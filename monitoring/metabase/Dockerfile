FROM python:3.11-slim

WORKDIR /app
RUN pip install --no-cache-dir requests
COPY setup_dashboards.py .

CMD ["python", "-u", "setup_dashboards.py"]
