# Jeevandhara — website + API in one container.
#
#   docker build -t jeevandhara .
#   docker run -p 8000:8000 -v jeevandhara-data:/data jeevandhara
#
# Then open http://localhost:8000/

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    JEEVANDHARA_DB=/data/jeevandhara.db

WORKDIR /app

COPY backend/requirements.txt backend/requirements.txt
RUN pip install -r backend/requirements.txt

COPY backend/ backend/
COPY frontend/ frontend/

# Run as a normal user; the database lives on the /data volume.
RUN useradd --create-home --uid 1000 jeevandhara \
    && mkdir -p /data \
    && chown jeevandhara:jeevandhara /data
USER jeevandhara
VOLUME ["/data"]

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4)"

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
