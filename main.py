from __future__ import annotations

import argparse
import json
from pathlib import Path

from srevices.gmail_airbnb_parser import GmailAirbnbReader


def load_emails(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)

    if isinstance(data, dict):
        data = data.get("emails", [])

    if not isinstance(data, list):
        raise ValueError("Expected a JSON list of emails or an object with an 'emails' list.")

    return data


def demo_emails() -> list[dict]:
    return [
        {
            "from": "Airbnb <no-reply@airbnb.com>",
            "subject": "Reservation confirmed",
            "body": (
                "Hi Jane Doe,\n"
                "Your Airbnb reservation is confirmed.\n"
                "Check-in: June 10, 2026\n"
                "Check-out: June 15, 2026\n"
                "Total paid: $1,245.67\n"
                "Guest: Jane Doe\n"
            ),
        }
    ]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Extract Airbnb reservation details from emails.")
    parser.add_argument(
        "input",
        nargs="?",
        type=Path,
        help="Optional path to a JSON file containing email objects.",
    )
    parser.add_argument(
        "--download",
        action="store_true",
        help="Download Airbnb emails from Gmail instead of reading a local JSON file.",
    )
    parser.add_argument(
        "--credentials",
        type=Path,
        default=Path("credentials.json"),
        help="Path to the Google OAuth client secrets file.",
    )
    parser.add_argument(
        "--token",
        type=Path,
        default=Path("token.json"),
        help="Path to the cached OAuth token file.",
    )
    parser.add_argument(
        "--max-results",
        type=int,
        default=100,
        help="Maximum number of Airbnb emails to download.",
    )
    parser.add_argument(
        "--query",
        default=None,
        help="Optional extra Gmail search terms to narrow the Airbnb download.",
    )
    return parser


def main() -> None:
    reader = GmailAirbnbReader(credentials_path=Path("client_secret_839974854169-0qe6aoi7726adu2278dr2kfpmgs8ldgd.apps.googleusercontent.com.json"))
    reservations = reader.get_reservations_for_month(2026, 4)

    for r in reservations:
        print(r)



if __name__ == "__main__":
    main()
