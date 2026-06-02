from __future__ import annotations

import json
import os
from pathlib import Path

from srevices.aade_declaration import AADEDeclaration


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _load_credentials_config(path: str) -> dict:
    file_path = Path(path)
    if not file_path.exists():
        return {}

    try:
        payload = json.loads(file_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Credentials file is not valid JSON: {file_path}") from exc

    if not isinstance(payload, dict):
        raise ValueError(
            f"Credentials file must contain a JSON object: {file_path}")

    return payload


def main() -> None:
    credentials_file = os.getenv("AADE_CREDENTIALS_FILE",
                                 "aade_credentials_secret.json")
    cfg = _load_credentials_config(credentials_file)

    username = os.getenv("AADE_USERNAME", str(cfg.get("username", "")))
    password = os.getenv("AADE_PASSWORD", str(cfg.get("password", "")))
    property_id = os.getenv("AADE_PROPERTY_ID",
                            str(cfg.get("property_id", "0000")))
    headless = _env_bool("AADE_HEADLESS",
                         default=bool(cfg.get("headless", False)))
    submit = _env_bool("AADE_SUBMIT", default=bool(cfg.get("submit", False)))
    screenshots = _env_bool("AADE_SCREENSHOTS",
                            default=bool(cfg.get("screenshots", False)))
    screenshots_dir = os.getenv("AADE_SCREENSHOTS_DIR",
                                str(cfg.get("screenshots_dir",
                                            "aade_screenshots")))

    declaration_data = {
        "arrival_date": "27/05/2026",
        "departure_date": "31/05/2026",
        "total_rent": "350,00",
        "payment_method": 'Μετρητά',
        "platform": 'Airbnb',
        "is_foreigner": True,
        "passport_id": "AB123456",
        "notes": "κωδικός_κράτησης:HMD2KFC4JB, test delete me",
        "reservation_id": "HMD2KFC4JB",
        "tenant_full_name": "John Doe",
    }
    aade = AADEDeclaration(
        headless=headless,
        property_id=property_id,
        screenshots_enabled=screenshots,
        screenshots_dir=screenshots_dir,
        username=username,
        password=password,
        timeout_seconds=60,
    )
    aade.create_new_declaration(declaration_data=declaration_data,
                                submit=submit,
                                save=True
                                )


if __name__ == "__main__":
    main()
