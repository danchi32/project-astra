# ASTRA Marketing Service — production image.
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Dependencies first, so a code change does not re-resolve the whole tree.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN chmod +x entrypoint.sh && \
    addgroup --system astra && adduser --system --ingroup astra astra && \
    chown -R astra:astra /app
USER astra

EXPOSE 8080
CMD ["./entrypoint.sh"]
