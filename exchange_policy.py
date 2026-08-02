from datetime import date, timedelta
from decimal import Decimal
from typing import Any, Dict, Optional


RETRY_DAYS = 5
PLAN_THRESHOLDS = (
    (Decimal("500"), "plan500"),
    (Decimal("200"), "plan200"),
    (Decimal("100"), "plan100"),
)


def select_exchange_plan(points: Optional[Decimal]) -> Optional[str]:
    if points is None:
        return None
    for threshold, plan in PLAN_THRESHOLDS:
        if points >= threshold:
            return plan
    return None


def record_checkin(task: Dict[str, Any], is_valid: bool, interval_days: int) -> None:
    if not is_valid or task["exchange_due"]:
        return
    task["valid_days"] = min(task["valid_days"] + 1, interval_days)
    if task["valid_days"] >= interval_days:
        task["exchange_due"] = True


def should_attempt_exchange(task: Dict[str, Any], today: date) -> bool:
    if not task["exchange_due"]:
        return False
    next_date = task.get("next_exchange_date")
    return next_date is None or today >= date.fromisoformat(next_date)


def schedule_retry(task: Dict[str, Any], today: date) -> None:
    task["next_exchange_date"] = (today + timedelta(days=RETRY_DAYS)).isoformat()


def reset_after_exchange(task: Dict[str, Any], today: date) -> None:
    task["valid_days"] = 0
    task["exchange_due"] = False
    task["next_exchange_date"] = None
    task["last_exchange_success_date"] = today.isoformat()
