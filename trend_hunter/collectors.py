from __future__ import annotations

import hashlib
import html
import re
from datetime import date, datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlencode
from xml.etree import ElementTree

import requests


UA = "AI-Trend-Hunter/0.2 (+local research tool)"


def _text(value: str | None) -> str:
    clean = re.sub(r"<[^>]+>", " ", html.unescape(value or ""))
    return re.sub(r"\s+", " ", clean).strip()


class Collectors:
    def __init__(self, timeout: int = 20, github_token: str = ""):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers["User-Agent"] = UA
        if github_token:
            self.session.headers["Authorization"] = f"Bearer {github_token}"

    def collect_all(self, limit: int = 8) -> tuple[list[dict[str, Any]], list[str]]:
        items, errors = [], []
        for name, method in (("GeekNews", self.geeknews), ("Hacker News", self.hacker_news), ("GitHub", self.github)):
            try:
                items.extend(method(limit))
            except Exception as exc:  # one source must not stop the run
                errors.append(f"{name}: {type(exc).__name__}: {exc}")
        return items, errors

    def geeknews(self, limit: int) -> list[dict[str, Any]]:
        response = self.session.get("https://news.hada.io/rss/news", timeout=self.timeout)
        response.raise_for_status()
        root = ElementTree.fromstring(response.content)
        output = []
        rss_items = root.findall(".//item")
        for node in rss_items[:limit]:
            title = _text(node.findtext("title"))
            url = (node.findtext("link") or "").strip()
            guid = (node.findtext("guid") or url or title).strip()
            output.append({"source": "GeekNews", "external_id": guid, "title": title, "url": url,
                           "published_at": node.findtext("pubDate"), "description": _text(node.findtext("description")),
                           "raw": {"guid": guid}})
        if output:
            return output
        # GeekNews currently redirects to a namespaced Atom feed.
        ns = {"a": "http://www.w3.org/2005/Atom"}
        for node in root.findall("a:entry", ns)[:limit]:
            title = _text(node.findtext("a:title", default="", namespaces=ns))
            link_node = node.find("a:link[@rel='alternate']", ns)
            if link_node is None:
                link_node = node.find("a:link", ns)
            url = (link_node.get("href", "") if link_node is not None else "").strip()
            guid = (node.findtext("a:id", default=url or title, namespaces=ns) or url or title).strip()
            author = node.findtext("a:author/a:name", default="", namespaces=ns)
            content = node.findtext("a:content", default="", namespaces=ns)
            output.append({"source": "GeekNews", "external_id": guid, "title": title, "url": url,
                           "author": author, "published_at": node.findtext("a:published", default="", namespaces=ns),
                           "description": _text(content), "raw": {"guid": guid}})
        return output

    def hacker_news(self, limit: int) -> list[dict[str, Any]]:
        ids = self.session.get("https://hacker-news.firebaseio.com/v0/topstories.json", timeout=self.timeout)
        ids.raise_for_status()
        output = []
        for story_id in ids.json()[:limit]:
            response = self.session.get(f"https://hacker-news.firebaseio.com/v0/item/{story_id}.json", timeout=self.timeout)
            response.raise_for_status()
            row = response.json() or {}
            if row.get("type") != "story" or not row.get("title"):
                continue
            output.append({"source": "Hacker News", "external_id": str(story_id), "title": row["title"],
                           "url": row.get("url") or f"https://news.ycombinator.com/item?id={story_id}",
                           "author": row.get("by"), "published_at": datetime.fromtimestamp(row.get("time", 0), timezone.utc).isoformat(),
                           "score": row.get("score"), "description": _text(row.get("text")), "raw": row})
        return output

    def github(self, limit: int) -> list[dict[str, Any]]:
        since = (date.today() - timedelta(days=90)).isoformat()
        query = f"(llm OR agent OR rag) created:>{since} stars:>20"
        params = urlencode({"q": query, "sort": "stars", "order": "desc", "per_page": min(limit, 30)})
        response = self.session.get(f"https://api.github.com/search/repositories?{params}", timeout=self.timeout)
        response.raise_for_status()
        output = []
        for row in response.json().get("items", [])[:limit]:
            output.append({"source": "GitHub", "external_id": str(row["id"]), "title": row["full_name"],
                           "url": row["html_url"], "author": row.get("owner", {}).get("login"),
                           "published_at": row.get("created_at"), "score": row.get("stargazers_count"),
                           "description": row.get("description") or "", "raw": row})
        return output


def stable_id(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:20]

