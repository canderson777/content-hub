"""Local, brand-scoped SQLite persistence for Content Hub review records."""

from __future__ import annotations

from datetime import date, datetime, timezone
import json
from pathlib import Path
import sqlite3
import threading
from typing import Any
from uuid import uuid4


VALID_BRANDS = {"brand-a", "brand-b", "brand-c"}
CONTENT_STATUSES = {
    "Draft",
    "Needs Review",
    "Changes Requested",
    "Skipped",
    "Approved",
    "Scheduled",
    "Confirmed Published",
}
MAX_BODY_LENGTH = 20_000
BRAND_PROFILE_FIELDS = (
    "voiceStyle",
    "audience",
    "offerAndLinks",
    "ctaStyle",
    "neverUse",
    "contentPillars",
    "positioning",
)
MAX_PROFILE_FIELD_LENGTH = 20_000
MAX_PROFILE_TOTAL_LENGTH = 80_000


class ContentError(Exception):
    """Expected content-store error with an HTTP status code."""

    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


class ContentStore:
    """Thread-safe SQLite store for submitted content and review decisions."""

    def __init__(self, database_path: str | Path):
        self.database_path = str(database_path)
        if self.database_path != ":memory:":
            Path(self.database_path).expanduser().parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._connection = sqlite3.connect(self.database_path, timeout=10, check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA foreign_keys = ON")
        self._connection.execute("PRAGMA busy_timeout = 10000")
        if self.database_path != ":memory:":
            self._connection.execute("PRAGMA journal_mode = WAL")
        self._initialize()

    def _initialize(self) -> None:
        with self._lock:
            version = self._connection.execute("PRAGMA user_version").fetchone()[0]
            if version > 2:
                raise RuntimeError(f"Content database schema {version} is newer than this app supports.")
            self._connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS content_records (
                    id TEXT PRIMARY KEY,
                    brand_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    content_type TEXT NOT NULL,
                    channel TEXT NOT NULL,
                    format TEXT NOT NULL,
                    body TEXT NOT NULL,
                    brief TEXT NOT NULL DEFAULT '',
                    source_url TEXT NOT NULL DEFAULT '',
                    source_module TEXT NOT NULL DEFAULT '',
                    source_id TEXT NOT NULL DEFAULT '',
                    target_date TEXT,
                    status TEXT NOT NULL CHECK (status IN (
                        'Draft', 'Needs Review', 'Changes Requested', 'Skipped',
                        'Approved', 'Scheduled', 'Confirmed Published'
                    )),
                    review_note TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    scheduled_at TEXT,
                    confirmed_published_at TEXT
                );
                CREATE INDEX IF NOT EXISTS content_records_brand_date
                    ON content_records (brand_id, target_date, created_at);
                CREATE TABLE IF NOT EXISTS brand_profiles (
                    brand_id TEXT PRIMARY KEY,
                    profile_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                PRAGMA user_version = 2;
                """
            )

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat(timespec="seconds")

    @staticmethod
    def _text(payload: dict[str, Any], key: str, limit: int, *, required: bool = False) -> str:
        value = payload.get(key, "")
        if not isinstance(value, str):
            raise ContentError(f"{key} must be text.")
        if len(value) > limit:
            raise ContentError(f"{key} exceeds the {limit}-character limit.")
        if required and not value.strip():
            raise ContentError(f"{key} is required.")
        return value

    @staticmethod
    def _date(value: Any) -> str | None:
        if value in (None, ""):
            return None
        if not isinstance(value, str):
            raise ContentError("targetDate must be a YYYY-MM-DD date or empty.")
        try:
            parsed = date.fromisoformat(value)
        except ValueError:
            raise ContentError("targetDate must be a valid YYYY-MM-DD date.") from None
        if parsed.isoformat() != value:
            raise ContentError("targetDate must be a valid YYYY-MM-DD date.")
        return value

    @staticmethod
    def _brand(brand_id: Any) -> str:
        if not isinstance(brand_id, str) or brand_id not in VALID_BRANDS:
            raise ContentError("Choose a configured brand.")
        return brand_id

    @staticmethod
    def _record(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "brandId": row["brand_id"],
            "title": row["title"],
            "contentType": row["content_type"],
            "channel": row["channel"],
            "format": row["format"],
            "body": row["body"],
            "brief": row["brief"],
            "sourceUrl": row["source_url"],
            "sourceModule": row["source_module"],
            "sourceId": row["source_id"],
            "targetDate": row["target_date"],
            "status": row["status"],
            "reviewNote": row["review_note"],
            "createdAt": row["created_at"],
            "updatedAt": row["updated_at"],
            "scheduledAt": row["scheduled_at"],
            "confirmedPublishedAt": row["confirmed_published_at"],
        }

    def create_submission(self, payload: Any) -> dict[str, Any]:
        return self._create_record(payload, "Needs Review")

    def create_draft(self, payload: Any) -> dict[str, Any]:
        return self._create_record(payload, "Draft")

    def _create_record(self, payload: Any, status: str) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise ContentError("A JSON object is required.")
        brand_id = self._brand(payload.get("brandId"))
        title = self._text(payload, "title", 200, required=True).strip()
        content_type = self._text(payload, "contentType", 40, required=True).strip()
        channel = self._text(payload, "channel", 40, required=True).strip()
        content_format = self._text(payload, "format", 60, required=True).strip()
        body = self._text(payload, "body", MAX_BODY_LENGTH, required=True)
        brief = self._text(payload, "brief", 2_000)
        source_url = self._text(payload, "sourceUrl", 2_000)
        source_module = self._text(payload, "sourceModule", 40)
        source_id = self._text(payload, "sourceId", 120)
        target_date = self._date(payload.get("targetDate"))
        now = self._now()
        record_id = str(uuid4())
        with self._lock:
            self._connection.execute(
                """INSERT INTO content_records (
                    id, brand_id, title, content_type, channel, format, body, brief,
                    source_url, source_module, source_id, target_date, status,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (record_id, brand_id, title, content_type, channel, content_format, body, brief,
                 source_url, source_module, source_id, target_date, status, now, now),
            )
            self._connection.commit()
            return self.get_record(record_id)

    def list_records(self, brand_id: Any) -> list[dict[str, Any]]:
        selected_brand = self._brand(brand_id)
        with self._lock:
            rows = self._connection.execute(
                """SELECT * FROM content_records WHERE brand_id = ?
                   ORDER BY CASE WHEN target_date IS NULL THEN 1 ELSE 0 END,
                            target_date ASC, created_at DESC""",
                (selected_brand,),
            ).fetchall()
        return [self._record(row) for row in rows]

    def get_record(self, record_id: str) -> dict[str, Any]:
        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM content_records WHERE id = ?", (record_id,)
            ).fetchone()
        if row is None:
            raise ContentError("Content record not found.", 404)
        return self._record(row)

    def apply_action(self, record_id: str, payload: Any) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise ContentError("A JSON object is required.")
        action = payload.get("action")
        if not isinstance(action, str):
            raise ContentError("An action is required.")
        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM content_records WHERE id = ?", (record_id,)
            ).fetchone()
            if row is None:
                raise ContentError("Content record not found.", 404)
            current = row["status"]
            now = self._now()

            if action == "save_draft" and current == "Draft":
                body = self._text(payload, "body", MAX_BODY_LENGTH, required=True)
                title = self._text(payload, "title", 200, required=True).strip()
                brief = row["brief"]
                if "brief" in payload:
                    brief = self._text(payload, "brief", 2_000)
                target_date = row["target_date"]
                if "targetDate" in payload:
                    target_date = self._date(payload.get("targetDate"))
                self._connection.execute(
                    """UPDATE content_records
                       SET title = ?, body = ?, brief = ?, target_date = ?, updated_at = ?
                       WHERE id = ?""",
                    (title, body, brief, target_date, now, record_id),
                )
            elif action == "submit_for_review" and current == "Draft":
                self._connection.execute(
                    "UPDATE content_records SET status = 'Needs Review', updated_at = ? WHERE id = ?",
                    (now, record_id),
                )
            elif action == "approve" and current == "Needs Review":
                self._connection.execute(
                    "UPDATE content_records SET status = 'Approved', updated_at = ? WHERE id = ?",
                    (now, record_id),
                )
            elif action == "edit" and current in {"Needs Review", "Changes Requested", "Approved"}:
                body = self._text(payload, "body", MAX_BODY_LENGTH, required=True)
                title = self._text(payload, "title", 200).strip() or row["title"]
                brief = row["brief"]
                if "brief" in payload:
                    brief = self._text(payload, "brief", 2_000)
                review_note = self._text(payload, "reviewNote", 1_000)
                target_date = row["target_date"]
                if "targetDate" in payload:
                    target_date = self._date(payload.get("targetDate"))
                self._connection.execute(
                    """UPDATE content_records
                       SET title = ?, body = ?, brief = ?, target_date = ?, review_note = ?,
                           status = 'Changes Requested', updated_at = ?
                       WHERE id = ?""",
                    (title, body, brief, target_date, review_note, now, record_id),
                )
            elif action == "resubmit" and current == "Changes Requested":
                self._connection.execute(
                    "UPDATE content_records SET status = 'Needs Review', updated_at = ? WHERE id = ?",
                    (now, record_id),
                )
            elif action == "skip" and current in {"Needs Review", "Changes Requested"}:
                self._connection.execute(
                    "UPDATE content_records SET status = 'Skipped', updated_at = ? WHERE id = ?",
                    (now, record_id),
                )
            elif action == "mark_scheduled" and current == "Approved":
                if not row["target_date"]:
                    raise ContentError("Add a target date before recording this item as scheduled.")
                self._connection.execute(
                    """UPDATE content_records SET status = 'Scheduled', scheduled_at = ?, updated_at = ?
                       WHERE id = ?""",
                    (now, now, record_id),
                )
            elif action == "confirm_published" and current == "Scheduled":
                self._connection.execute(
                    """UPDATE content_records
                       SET status = 'Confirmed Published', confirmed_published_at = ?, updated_at = ?
                       WHERE id = ?""",
                    (now, now, record_id),
                )
            else:
                raise ContentError(
                    f"Invalid status transition: cannot apply action '{action}' while status is '{current}'.", 409
                )
            self._connection.commit()
            return self.get_record(record_id)

    def get_brand_profile_override(self, brand_id: Any) -> dict[str, Any] | None:
        selected_brand = self._brand(brand_id)
        with self._lock:
            row = self._connection.execute(
                "SELECT profile_json, updated_at FROM brand_profiles WHERE brand_id = ?",
                (selected_brand,),
            ).fetchone()
        if row is None:
            return None
        try:
            fields = json.loads(row["profile_json"])
        except json.JSONDecodeError as error:
            raise RuntimeError("Saved brand profile data is invalid.") from error
        if not isinstance(fields, dict):
            raise RuntimeError("Saved brand profile data is invalid.")
        return {"fields": fields, "savedAt": row["updated_at"]}

    def save_brand_profile_override(self, brand_id: Any, fields: Any) -> dict[str, Any]:
        selected_brand = self._brand(brand_id)
        if not isinstance(fields, dict):
            raise ContentError("Profile fields must be a JSON object.")
        field_names = set(fields)
        expected_names = set(BRAND_PROFILE_FIELDS)
        if field_names != expected_names:
            missing = sorted(expected_names - field_names)
            unexpected = sorted(field_names - expected_names)
            details = []
            if missing:
                details.append(f"missing: {', '.join(missing)}")
            if unexpected:
                details.append(f"unexpected: {', '.join(unexpected)}")
            raise ContentError(f"Profile fields do not match the supported profile: {'; '.join(details)}.")

        validated: dict[str, str] = {}
        for field_name in BRAND_PROFILE_FIELDS:
            value = fields[field_name]
            if not isinstance(value, str):
                raise ContentError(f"{field_name} must be text.")
            if len(value) > MAX_PROFILE_FIELD_LENGTH:
                raise ContentError(f"{field_name} exceeds the {MAX_PROFILE_FIELD_LENGTH}-character limit.")
            validated[field_name] = value
        if sum(len(value) for value in validated.values()) > MAX_PROFILE_TOTAL_LENGTH:
            raise ContentError(f"Brand profile exceeds the {MAX_PROFILE_TOTAL_LENGTH}-character total limit.")

        saved_at = self._now()
        profile_json = json.dumps(validated, ensure_ascii=False, sort_keys=True)
        with self._lock:
            self._connection.execute(
                """INSERT INTO brand_profiles (brand_id, profile_json, updated_at)
                   VALUES (?, ?, ?)
                   ON CONFLICT(brand_id) DO UPDATE SET
                       profile_json = excluded.profile_json,
                       updated_at = excluded.updated_at""",
                (selected_brand, profile_json, saved_at),
            )
            self._connection.commit()
        return {"fields": validated, "savedAt": saved_at}

    def reset_brand_profile_override(self, brand_id: Any) -> None:
        selected_brand = self._brand(brand_id)
        with self._lock:
            self._connection.execute("DELETE FROM brand_profiles WHERE brand_id = ?", (selected_brand,))
            self._connection.commit()

    def close(self) -> None:
        with self._lock:
            self._connection.close()
