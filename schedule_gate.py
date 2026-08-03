import argparse
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from state_store import StateStore


BEIJING_TZ = timezone(timedelta(hours=8))


@dataclass(frozen=True)
class GateDecision:
    should_run: bool
    reason: str
    beijing_date: str


def decide(
    now: datetime,
    last_complete_date: Optional[str],
) -> GateDecision:
    beijing_now = now.astimezone(BEIJING_TZ)
    today = beijing_now.date().isoformat()

    if last_complete_date == today:
        return GateDecision(False, "今天已经完成签到", today)
    return GateDecision(True, "今天尚未完成，立即执行", today)


def write_github_output(path: str, decision: GateDecision) -> None:
    with Path(path).open("a", encoding="utf-8") as output:
        output.write(f"should_run={'true' if decision.should_run else 'false'}\n")
        output.write(f"beijing_date={decision.beijing_date}\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="决定今天的 GLaDOS 签到任务是否应执行")
    parser.add_argument("--state-file", default=".state/checkin-state.json")
    parser.add_argument("--github-output", default=os.environ.get("GITHUB_OUTPUT"))
    args = parser.parse_args()

    store = StateStore(args.state_file)
    now = datetime.now(timezone.utc)
    decision = decide(now, store.last_complete_date)
    if store.warning:
        print(f"警告: {store.warning}")
    print(
        f"北京时间日期 {decision.beijing_date}，"
        f"should_run={str(decision.should_run).lower()}：{decision.reason}"
    )
    if args.github_output:
        write_github_output(args.github_output, decision)


if __name__ == "__main__":
    main()
