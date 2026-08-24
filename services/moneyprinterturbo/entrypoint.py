#!/usr/bin/env python
"""Entrypoint wrapper for MoneyPrinterTurbo API-only mode on Fly.

Merges ENV-provided API keys into config.toml at startup (before uvicorn),
because MPT's config loader reads config.toml only — no env override exists
(get_api_key in app/services/material.py reads config.app directly).

ENV keys merged (comma-separated lists accepted):
  PEXELS_API_KEYS, PIXABAY_API_KEYS, COVERR_API_KEYS, MPT_API_KEY (app.api_key)

Never logs key values. Writes are atomic (tmp file + rename).
"""
import os
import shutil
import sys
import tempfile

CONFIG_PATH = "/MoneyPrinterTurbo/config.toml"

# ENV name -> [toml_section, toml_key, is_list]
MAPPINGS = {
    "PEXELS_API_KEYS": ["app", "pexels_api_keys", True],
    "PIXABAY_API_KEYS": ["pixabay_api_keys", "pixabay_api_keys", True],
    "COVERR_API_KEYS": ["coverr_api_keys", "coverr_api_keys", True],
    "MPT_API_KEY": ["app", "api_key", False],
}


def merge_list_key(text: str, key: str, values: list[str]) -> str:
    """Replace `key = [...]` (or `key = []`) with the ENV-provided list."""
    import re
    pattern = re.compile(rf"^{re.escape(key)}\s*=\s*\[.*\]", re.MULTILINE)
    new_line = f"{key} = [" + ", ".join(f'"{v}"' for v in values) + "]"
    if pattern.search(text):
        return pattern.sub(new_line, text, count=1)
    # key not present in file — append under [app] section (or at end)
    if "[app]" in text:
        return text.replace("[app]", f"[app]\n{new_line}", 1)
    return text + "\n\n[app]\n" + new_line + "\n"


def merge_scalar_key(text: str, key: str, value: str) -> str:
    import re
    pattern = re.compile(rf"^{re.escape(key)}\s*=\s*\"[^\"]*\"", re.MULTILINE)
    new_line = f'{key} = "{value}"'
    if pattern.search(text):
        return pattern.sub(new_line, text, count=1)
    if "[app]" in text:
        return text.replace("[app]", f"[app]\n{new_line}", 1)
    return text + "\n\n[app]\n" + new_line + "\n"


def main() -> int:
    # Base image's own entrypoint normally copies config.example.toml ->
    # config.toml on first run; we replaced that entrypoint, so do it here.
    if not os.path.exists(CONFIG_PATH):
        example = CONFIG_PATH.replace("config.toml", "config.example.toml")
        if os.path.exists(example):
            shutil.copyfile(example, CONFIG_PATH)
            print("[entrypoint] created config.toml from example", flush=True)
        else:
            # no example either — start from a minimal file
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                f.write('[app]\nlisten_host = "::"\nlisten_port = 8080\n')
            print("[entrypoint] created minimal config.toml", flush=True)

    with open(CONFIG_PATH, encoding="utf-8") as f:
        text = f.read()

    changed = False
    for env_name, (section, key, is_list) in MAPPINGS.items():
        raw = os.environ.get(env_name, "").strip()
        if not raw:
            continue
        if is_list:
            values = [v.strip() for v in raw.split(",") if v.strip()]
            if not values:
                continue
            new_text = merge_list_key(text, key, values)
        else:
            new_text = merge_scalar_key(text, key, raw)
        if new_text != text:
            text = new_text
            changed = True
            print(f"[entrypoint] merged {env_name} -> config.toml ({key})", flush=True)

    if changed:
        fd, tmp = tempfile.mkstemp(dir="/MoneyPrinterTurbo", suffix=".toml")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp, CONFIG_PATH)
        print("[entrypoint] config.toml updated", flush=True)
    else:
        print("[entrypoint] no ENV overrides present", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
