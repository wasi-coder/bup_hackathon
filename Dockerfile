FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt && useradd --create-home appuser

COPY src ./src
COPY start.py ./start.py

USER appuser

ENV PORT=8000 \
    PYTHONUNBUFFERED=1 \
    GROQ_MODEL="openai/gpt-oss-20b" \
    GROQ_TEMPERATURE=0 \
    GROQ_ATTEMPTS=2 \
    LLM_CACHE_SIZE=256

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=4s --start-period=60s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)"

CMD ["python", "-m", "start"]
