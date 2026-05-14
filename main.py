from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

from srevices.gmai_reader import GmailReader
from srevices.gmail_airbnb_parser import AirbnbMailParser
from srevices.reservation_store import ReservationStore


def default_credentials_path() -> Path:
    candidates = [Path("credentials.json"), Path("client_secret.json"), *sorted(Path.cwd().glob("client_secret_*.json"))]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return Path("credentials.json")


def build_reservation_gmail_query(year: int, month: int, extra_query: str | None = None) -> str:
    start = datetime(year, month, 1)
    end = datetime(year + (month // 12), (month % 12) + 1, 1)
    query = (
        f'from:airbnb (subject:"Reservation confirmed" OR subject:"Canceled: Reservation") '
        f"after:{start.strftime('%Y/%m/%d')} before:{end.strftime('%Y/%m/%d')}"
    )
    if extra_query:
        query = f"{query} {extra_query.strip()}"
    return query


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Extract Airbnb reservation details from emails.")
    parser.add_argument(
        "input",
        nargs="?",
        type=Path,
        help="Optional path to a JSON file containing email objects.",
    )
    parser.add_argument(
        "--credentials",
        type=Path,
        default=default_credentials_path(),
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
    parser.add_argument(
        "--db-path",
        type=Path,
        default=Path("reservations_db.json"),
        help="Path to the TinyDB JSON file used to store reservations.",
    )
    parser.add_argument(
        "--year",
        type=int,
        default=datetime.now().year,
        help="Year to use for the Gmail date range filter.",
    )
    parser.add_argument(
        "--month",
        type=int,
        default=datetime.now().month,
        choices=range(1, 13),
        help="Month to use for the Gmail date range filter.",
    )
    return parser




def main() -> None:
    args = build_parser().parse_args()
    query = build_reservation_gmail_query(args.year, args.month, args.query)

    reader = GmailReader(credentials_path=str(args.credentials), token_path=str(args.token))
    messages = reader.list_messages(query=query, max_results=args.max_results)

    parser = AirbnbMailParser(messages=messages)
    reservations = parser.get_reservations()

    store = ReservationStore(args.db_path, table_name="reservations")
    try:
        summary = store.save_many(reservations)
    finally:
        store.close()

    print(
        f"Saved {summary['saved']} reservations to {args.db_path} "
        f"({summary['inserted']} inserted, {summary['updated']} updated)."
    )
    for reservation in reservations:
        print(json.dumps(reservation, ensure_ascii=False))





if __name__ == "__main__":
    main()
