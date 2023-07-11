FROM python:3.11.4-slim-bullseye

COPY requirements.txt .
RUN pip install -r requirements.txt
RUN rm -rf /var/lib/apt/lists/*

COPY . .

CMD ["python", "main.py", "--polling"]
