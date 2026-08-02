import hashlib
import json
import os
import shutil
import tempfile
from copy import deepcopy
from datetime import date
from pathlib import Path
from typing import Any, Dict, Optional


STATE_VERSION = 1


def _empty_state() -> Dict[str, Any]:
    return {
        "version": STATE_VERSION,
        "last_complete_date": None,
        "tasks": {},
    }


def _empty_task(domain: str) -> Dict[str, Any]:
    return {
        "domain": domain,
        "last_attempt_date": None,
        "valid_days": 0,
        "exchange_due": False,
        "next_exchange_date": None,
        "last_exchange_success_date": None,
    }


class StateStore:
    """Versioned JSON state persisted atomically between workflow runs."""

    def __init__(self, path: str):
        self.path = Path(path)
        self.warning: Optional[str] = None
        self.data = self._load()

    def _load(self) -> Dict[str, Any]:
        if not self.path.exists():
            return _empty_state()

        try:
            with self.path.open("r", encoding="utf-8") as state_file:
                data = json.load(state_file)
            if data.get("version") != STATE_VERSION:
                raise ValueError(f"不支持的状态版本: {data.get('version')}")
            if not isinstance(data.get("tasks"), dict):
                raise ValueError("状态中的 tasks 必须是对象")
            return data
        except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
            self.warning = f"状态文件无法读取，将重新计时: {exc}"
            self._preserve_corrupt_file()
            return _empty_state()

    def _preserve_corrupt_file(self) -> None:
        try:
            backup = self.path.with_name(f"{self.path.name}.corrupt")
            shutil.copy2(self.path, backup)
        except OSError:
            pass

    @staticmethod
    def task_id(cookie: str, domain: str) -> str:
        value = f"{domain}\0{cookie}".encode("utf-8")
        return hashlib.sha256(value).hexdigest()

    @property
    def last_complete_date(self) -> Optional[str]:
        return self.data.get("last_complete_date")

    def get_task(self, task_id: str, domain: str) -> Dict[str, Any]:
        task = self.data["tasks"].setdefault(task_id, _empty_task(domain))
        return deepcopy(task)

    def update_task(self, task_id: str, task: Dict[str, Any]) -> None:
        self.data["tasks"][task_id] = deepcopy(task)
        self.save()

    def mark_complete(self, day: date) -> None:
        self.data["last_complete_date"] = day.isoformat()
        self.save()

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temp_path = tempfile.mkstemp(
            prefix=f".{self.path.name}.",
            dir=str(self.path.parent),
            text=True,
        )
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as state_file:
                json.dump(self.data, state_file, ensure_ascii=False, indent=2, sort_keys=True)
                state_file.write("\n")
                state_file.flush()
                os.fsync(state_file.fileno())
            os.replace(temp_path, self.path)
        except Exception:
            try:
                os.unlink(temp_path)
            except OSError:
                pass
            raise
