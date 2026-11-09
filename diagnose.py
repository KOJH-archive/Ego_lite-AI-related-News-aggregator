from __future__ import annotations

import argparse
import json

from trend_hunter.config import Settings
from trend_hunter.diagnostics import run_diagnostics


parser = argparse.ArgumentParser()
parser.add_argument("--live-browser", action="store_true")
args = parser.parse_args()
checks = run_diagnostics(Settings(), live_browser=args.live_browser)
print(json.dumps(checks, ensure_ascii=False, indent=2))
raise SystemExit(0 if all(row["ok"] for row in checks) else 1)

