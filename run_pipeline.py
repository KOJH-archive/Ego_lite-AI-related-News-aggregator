from __future__ import annotations

import argparse
import json

from trend_hunter.config import Settings
from trend_hunter.pipeline import Pipeline


parser = argparse.ArgumentParser()
parser.add_argument("--no-browser", action="store_true", help="ego(lite) 탐색을 건너뜁니다.")
args = parser.parse_args()
report = Pipeline(Settings(), print).run(use_browser=not args.no_browser)
print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
raise SystemExit(0 if report.status in {"completed", "partial"} else 1)

