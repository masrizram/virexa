# MoneyPrinterTurbo — headless API mode for Virexa.
# Base image ships a WebUI entrypoint; we override it to run the FastAPI/ASGI
# server (app.asgi:app) directly, bound dual-stack so Fly 6PN (.internal) works.
FROM ghcr.io/harry0703/moneyprinterturbo:latest

ENV API_AUTH=false \
    WHISPER_METHOD=none \
    UVICORN_WORKERS=1

WORKDIR /MoneyPrinterTurbo

# Dual-stack bind (::) — Fly private network uses IPv6 6PN addresses.
CMD ["python", "-m", "uvicorn", "app.asgi:app", "--host", "::", "--port", "8080"]

EXPOSE 8080
