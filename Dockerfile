FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN chmod +x start.sh

EXPOSE 80

ENV PORT=80
ENV RUN_MIGRATIONS_ON_STARTUP=false

CMD ["./start.sh"]
