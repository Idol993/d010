import json
import os
import uuid
from datetime import datetime

from .models import ComplianceLogEntry
from .config import COMPLIANCE_LOG_FILE


class ComplianceLogger:
    def __init__(self):
        self._logs: list[ComplianceLogEntry] = []
        self._load()

    def log(self, operation: str, operator: str, details: str, release_id: str = "") -> ComplianceLogEntry:
        entry = ComplianceLogEntry(
            id=str(uuid.uuid4())[:8],
            operation=operation,
            operator=operator,
            details=details,
            release_id=release_id,
            timestamp=datetime.now(),
        )
        self._logs.append(entry)
        self._save()
        return entry

    def query(self, release_id: str = "", operation: str = "", start_time: datetime = None, end_time: datetime = None) -> list:
        results = self._logs
        if release_id:
            results = [e for e in results if e.release_id == release_id]
        if operation:
            results = [e for e in results if e.operation == operation]
        if start_time:
            results = [e for e in results if e.timestamp and e.timestamp >= start_time]
        if end_time:
            results = [e for e in results if e.timestamp and e.timestamp <= end_time]
        return results

    def get_all(self) -> list:
        return list(self._logs)

    def _save(self):
        dir_path = os.path.dirname(COMPLIANCE_LOG_FILE)
        if dir_path:
            os.makedirs(dir_path, exist_ok=True)
        data = []
        for entry in self._logs:
            data.append({
                "id": entry.id,
                "operation": entry.operation,
                "operator": entry.operator,
                "details": entry.details,
                "release_id": entry.release_id,
                "timestamp": entry.timestamp.isoformat() if entry.timestamp else "",
            })
        with open(COMPLIANCE_LOG_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _load(self):
        if not os.path.exists(COMPLIANCE_LOG_FILE):
            self._logs = []
            return
        with open(COMPLIANCE_LOG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        self._logs = []
        for item in data:
            ts = item.get("timestamp", "")
            self._logs.append(ComplianceLogEntry(
                id=item.get("id", ""),
                operation=item.get("operation", ""),
                operator=item.get("operator", ""),
                details=item.get("details", ""),
                release_id=item.get("release_id", ""),
                timestamp=datetime.fromisoformat(ts) if ts else None,
            ))
