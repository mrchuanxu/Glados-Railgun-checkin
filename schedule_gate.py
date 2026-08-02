import argparse
import hashlib
import os
from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from typing import Optional

from state_store import StateStore


BEIJING_TZ = timezone(timedelta(hours=8))
FIRST_SLOT_MINUTE = 12 * 60
LAST_SLOT_MINUTE = 17 * 60 + 45
SLOT_MINUTES = 15


@dataclass(frozen=True)
class GateDecision:
    should_run: bool
    reason: str
    target_time: str
    beijing_date: str


def daily_target(repository: str, now: datetime) -> datetime:
    beijing_now = now.astimezone(BEIJING_TZ)
    seed = f"{repository}\0{beijing_now.date().isoformat()}".encode("utf-8")
    digest = hashlib.sha256(seed).digest()
    slot_count = ((LAST_SLOT_MINUTE - FIRST_SLOT_MINUTE) // SLOT_MINUTES) + 1
    slot = int.from_bytes(digest[:8], "big") % slot_count
    minute_of_day = FIRST_SLOT_MINUTE + slot * SLOT_MINUTES
    target = datetime.combine(
        beijing_now.date(),
        time(hour=minute_of_day // 60, minute=minute_of_day % 60),
        tzinfo=BEIJING_TZ,
    )
    return target


def decide(
    now: datetime,
    event_name: str,
    repository: str,
    last_complete_date: Optional[str],
) -> GateDecision:
    beijing_now = now.astimezone(BEIJING_TZ)
    today = beijing_now.date().isoformat()
    target = daily_target(repository, now)
    target_text = target.strftime("%H:%M")

    if last_complete_date == today:
        return GateDecision(False, "今天已经完成签到", target_text, today)
    if event_name == "workflow_dispatch":
        return GateDecision(True, "手动触发且今天尚未执行", target_text, today)
    if beijing_now >= target:
        return GateDecision(True, "已到达今天的随机执行时间", target_text, today)
    return GateDecision(False, "尚未到达今天的随机执行时间", target_text, today)


def write_github_output(path: str, decision: GateDecision) -> None:
    with Path(path).open("a", encoding="utf-8") as output:
        output.write(f"should_run={'true' if decision.should_run else 'false'}\n")
        output.write(f"target_time={decision.target_time}\n")
        output.write(f"beijing_date={decision.beijing_date}\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="决定今天的 GLaDOS 签到任务是否应执行")
    parser.add_argument("--state-file", default=".state/checkin-state.json")
    parser.add_argument("--event-name", default=os.environ.get("GITHUB_EVENT_NAME", "schedule"))
    parser.add_argument("--repository", default=os.environ.get("GITHUB_REPOSITORY", "local/repository"))
    parser.add_argument("--github-output", default=os.environ.get("GITHUB_OUTPUT"))
    args = parser.parse_args()

    store = StateStore(args.state_file)
    now = datetime.now(timezone.utc)
    decision = decide(now, args.event_name, args.repository, store.last_complete_date)
    if store.warning:
        print(f"警告: {store.warning}")
    print(
        f"北京时间日期 {decision.beijing_date}，随机目标 {decision.target_time}，"
        f"should_run={str(decision.should_run).lower()}：{decision.reason}"
    )
    if args.github_output:
        write_github_output(args.github_output, decision)


if __name__ == "__main__":
    main()
