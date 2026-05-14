from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

from tinydb import Query, TinyDB


class ReservationStore:
    def __init__(self, db_path: str | Path, table_name: str = "reservations") -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db = TinyDB(self.db_path)
        self._table = self._db.table(table_name)

    def _reservation_key(self, reservation: dict) -> str:
        reservation_id = reservation.get("reservation_id")
        if reservation_id:
            return f"reservation_id:{reservation_id}"

        fallback_parts = [
            reservation.get("guest", ""),
            reservation.get("checkin", ""),
            reservation.get("checkout", ""),
            reservation.get("host_payout", ""),
        ]
        return "fallback:" + "|".join(str(part).strip() for part in fallback_parts)

    def save_many(self, reservations: list[dict]) -> dict[str, int]:
        summary = {"saved": len(reservations), "inserted": 0, "updated": 0}
        reservation_query = Query()

        for reservation in reservations:
            record = deepcopy(reservation)
            timestamp = datetime.now(timezone.utc).isoformat()
            record_key = self._reservation_key(record)
            record["reservation_key"] = record_key
            record["updated_at"] = timestamp

            existing = self._table.get(reservation_query.reservation_key == record_key)
            if existing:
                record["created_at"] = existing.get("created_at", timestamp)
                self._table.update(record, reservation_query.reservation_key == record_key)
                summary["updated"] += 1
            else:
                record["created_at"] = timestamp
                self._table.insert(record)
                summary["inserted"] += 1

        return summary

    def close(self) -> None:
        self._db.close()
