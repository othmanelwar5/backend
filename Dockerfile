FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN sed -i 's/\r$//' start.sh && chmod +x start.sh

EXPOSE 80

ENV RUN_MIGRATIONS_ON_STARTUP=false

HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.environ.get('PORT', '80') + '/health/live', timeout=3)" || exit 1

CMD ["sh", "start.sh"]
