# ASTRA backend — production image.
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app/backend

# Install dependencies first for better layer caching.
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .

RUN chmod +x entrypoint.sh && \
    addgroup --system astra && adduser --system --ingroup astra astra && \
    chown -R astra:astra /app
USER astra

EXPOSE 8000
CMD ["./entrypoint.sh"]
