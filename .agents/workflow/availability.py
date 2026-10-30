#!/usr/bin/env python3
"""Update one participant's check-in in a shared roster file."""
import argparse
import json
import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--team", type=Path, required=True)
    parser.add_argument("--login", required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--hours", type=float, help="check in for this many hours")
    mode.add_argument("--away", action="store_true")
    args = parser.parse_args()
    if args.hours is not None and not 0 < args.hours <= 24:
        parser.error("--hours must be greater than 0 and no more than 24")
    data = json.loads(args.team.read_text(encoding="utf-8-sig"))
    members = [m for m in data["members"] if m["login"].casefold() == args.login.casefold()]
    if len(members) != 1:
        parser.error("login must match exactly one configured team member")
    if args.away:
        members[0]["availability"] = {"state": "away"}
    else:
        end = datetime.now(timezone.utc) + timedelta(hours=args.hours)
        members[0]["availability"] = {"state": "working", "until": end.isoformat(timespec="seconds").replace("+00:00", "Z")}
    output = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    temp = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=args.team.parent, delete=False) as handle:
            temp = handle.name
            handle.write(output)
        os.replace(temp, args.team)
    finally:
        if temp and os.path.exists(temp):
            os.unlink(temp)
    print(f"Updated {args.login}: {members[0]['availability']}. Commit and push this file to share the change.")


if __name__ == "__main__":
    main()
