# MoneyPrinterTurbo image with config for headless API-only operation.
FROM ghcr.io/harry0703/moneyprinterturbo:latest

ENV API_AUTH=false \
    APP_VIRTUAL_PATH="" \
    WHISPER_METHOD=none

# MPT listens on 8080 by default (web + /v1 API).
EXPOSE 8080
