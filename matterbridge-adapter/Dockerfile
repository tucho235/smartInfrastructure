FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY adapter.py .

CMD ["python", "-u", "adapter.py"]
