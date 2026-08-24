# MoneyPrinterTurbo — headless API mode for Virexa.
# Base image ships a WebUI entrypoint; we override it to run the FastAPI/ASGI
# server (app.asgi:app) directly, bound dual-stack so Fly 6PN (.internal) works.
FROM ghcr.io/harry0703/moneyprinterturbo:latest

ENV API_AUTH=false \
    WHISPER_METHOD=none \
    UVICORN_WORKERS=1

WORKDIR /MoneyPrinterTurbo

# Entrypoint wrapper: merges ENV API keys (PEXELS_API_KEYS etc.) into
# config.toml at startup — MPT reads config.toml only, no env override exists.
COPY entrypoint.py /MoneyPrinterTurbo/entrypoint.py

# Dual-stack bind (::) — Fly private network uses IPv6 6PN addresses.
# Shell form so `&&` chains entrypoint + uvicorn; exec replaces the shell so
# uvicorn receives signals directly (clean stops, no zombie shell).
CMD python entrypoint.py && exec python -m uvicorn app.asgi:app --host :: --port 8080
