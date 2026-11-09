from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any


MARKER = "AI_TREND_HUNTER_JSON="


def _file_uri(path: Path) -> str:
    return path.resolve().as_uri()


class EgoBrowser:
    def __init__(self, timeout: int = 120):
        self.timeout = timeout

    def diagnostic(self) -> dict[str, Any]:
        executable = shutil.which("ego-browser")
        if not executable:
            return {"ok": False, "status": "not_installed", "message": "ego-browser 명령을 찾지 못했습니다."}
        try:
            result = subprocess.run([executable, "skill"], capture_output=True, text=True,
                                    encoding="utf-8", errors="replace", timeout=20)
            complete = "[ego-browser:skill] end of guide" in result.stdout
            return {"ok": result.returncode == 0 and complete, "status": "cli_ready" if complete else "skill_incomplete",
                    "message": "공식 Skill 가이드를 정상적으로 읽었습니다." if complete else (result.stderr or result.stdout)[-500:]}
        except Exception as exc:
            return {"ok": False, "status": "cli_error", "message": f"{type(exc).__name__}: {exc}"}

    def browse(self, urls: list[str], task_name: str, finish: bool = True) -> tuple[list[dict[str, Any]], str]:
        executable = shutil.which("ego-browser")
        if not executable:
            raise RuntimeError("ego-browser CLI가 설치되어 있지 않습니다.")
        safe_urls = [url for url in urls if url.startswith(("https://", "http://"))]
        script = self._script(safe_urls, task_name, finish)
        with tempfile.TemporaryDirectory(prefix="ai-trend-hunter-ego-") as directory:
            path = Path(directory) / "browse.mjs"
            path.write_text(script, encoding="utf-8")
            command = [executable, "nodejs", "-e", f"await import('{_file_uri(path)}')"]
            try:
                result = subprocess.run(command, capture_output=True, text=True,
                                        encoding="utf-8", errors="replace", timeout=self.timeout)
            except subprocess.TimeoutExpired as exc:
                raise RuntimeError("ego(lite) 응답 시간이 초과되었습니다. 브라우저 실행/연결 상태를 확인하세요.") from exc
        combined = (result.stdout or "") + "\n" + (result.stderr or "")
        if result.returncode != 0:
            if "cannot connect to the ego_cli bootstrap" in combined:
                raise RuntimeError("ego(lite) bootstrap 연결이 차단되었습니다. 앱을 직접 실행하고 격리되지 않은 PowerShell에서 진단하세요.")
            raise RuntimeError(f"ego-browser 실행 실패: {combined[-1200:].strip()}")
        line = next((line for line in combined.splitlines() if line.startswith(MARKER)), None)
        if not line:
            raise RuntimeError(f"ego-browser 결과 마커가 없습니다: {combined[-800:].strip()}")
        return json.loads(line[len(MARKER):]), "ego-lite"

    def finish(self, task_name: str) -> None:
        executable = shutil.which("ego-browser")
        if not executable:
            return
        script = f"const task = await taskSpace({json.dumps(task_name)}); await task.finish({{ keep: [] }});"
        with tempfile.TemporaryDirectory(prefix="ai-trend-hunter-ego-") as directory:
            path = Path(directory) / "finish.mjs"
            path.write_text(script, encoding="utf-8")
            subprocess.run([executable, "nodejs", "-e", f"await import('{_file_uri(path)}')"],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30)

    @staticmethod
    def _script(urls: list[str], task_name: str, finish: bool = True) -> str:
        urls_json = json.dumps(urls, ensure_ascii=False)
        name_json = json.dumps(task_name, ensure_ascii=False)
        finish_line = "await task.finish({ keep: [] });" if finish else ""
        return f"""const urls = {urls_json};
const task = await taskSpace({name_json});
const page = task.page('p1');
const results = [];
try {{
  for (const url of urls) {{
    try {{
      await page.goto(url, {{ timeout: 30000 }});
      await page.waitForLoadState('domcontentloaded');
      const data = await page.evaluate(() => {{
        const title = document.title || '';
        const root = document.querySelector('article, main, [role=main]') || document.body;
        const content = (root?.innerText || '').replace(/\\s+/g, ' ').trim().slice(0, 12000);
        const links = [...document.querySelectorAll('a[href]')]
          .map(a => ({{ text: (a.innerText || '').trim().slice(0, 100), url: a.href }}))
          .filter(x => x.text && /^https?:/.test(x.url))
          .slice(0, 30);
        return {{ title, content, links }};
      }});
      results.push({{ url: await page.url(), ...data }});
    }} catch (error) {{ results.push({{ url, error: String(error), content: '', links: [] }}); }}
  }}
  console.log('{MARKER}' + JSON.stringify(results));
}} finally {{
  {finish_line}
}}
"""

