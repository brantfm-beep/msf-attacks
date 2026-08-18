#!/usr/bin/env python3
"""Local development server for MSF Attack Planner Web.

Serves the static web app and provides one same-origin endpoint that loads a
Marvel Church Team Breakdown server-side. This mirrors the desktop app's
team-roster lookup while avoiding browser CORS restrictions during local tests.
"""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.parse
import urllib.request
import urllib.error
from html.parser import HTMLParser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DIRECTORY_FILE = ROOT / "data" / "team-directory.json"
CACHE_FILE = ROOT / ".team-rosters-cache.json"
CHARACTER_CACHE_FILE = ROOT / ".characters-cache.json"
PORT = int(os.environ.get("PORT", "8081"))


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


class TeamMemberParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.in_section = False
        self.capture_heading = False
        self.heading_parts = []
        self.capture_link = False
        self.link_href = ""
        self.link_parts = []
        self.members = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        tag = tag.lower()
        element_id = attrs.get("id", "").strip().lower()

        if element_id == "team-members":
            self.in_section = True

        if tag in ("h2", "h3"):
            if self.in_section and element_id != "team-members":
                # The next major heading ends the Team Members section.
                self.in_section = False
            self.capture_heading = True
            self.heading_parts = []

        if self.in_section and tag == "a":
            href = attrs.get("href", "").strip()
            if href.startswith("https://www.marvel.church/"):
                self.capture_link = True
                self.link_href = href
                self.link_parts = []

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in ("h2", "h3") and self.capture_heading:
            heading = clean_text(" ".join(self.heading_parts)).casefold()
            if heading == "team members":
                self.in_section = True
            self.capture_heading = False
            self.heading_parts = []

        if tag == "a" and self.capture_link:
            txt = clean_text(" ".join(self.link_parts))
            low = txt.casefold()
            if txt and low not in {"marvel church", "discord", "search new team"} and txt not in self.members:
                self.members.append(txt)
            self.capture_link = False
            self.link_href = ""
            self.link_parts = []

    def handle_data(self, data):
        if self.capture_heading:
            self.heading_parts.append(data)
        if self.capture_link:
            self.link_parts.append(data)


def parse_team_members(html: str):
    parser = TeamMemberParser()
    parser.feed(html)
    if len(parser.members) < 5:
        raise ValueError(f"Only found {len(parser.members)} team members; expected 5.")
    return parser.members[:5]


def fetch_with_urllib(url: str) -> str:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/151 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml",
        },
    )
    with urllib.request.urlopen(req, timeout=25) as response:
        return response.read().decode("utf-8", errors="replace")


def fetch_with_playwright(url: str) -> str:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        try:
            page = browser.new_page(
                viewport={"width": 1280, "height": 900},
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151 Safari/537.36",
            )
            page.goto(url, wait_until="domcontentloaded", timeout=45000)
            page.wait_for_selector("#team-members", timeout=20000)
            return page.content()
        finally:
            browser.close()


def load_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def save_cache(cache):
    try:
        CACHE_FILE.write_text(json.dumps(cache, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass



def fetch_json_url(url: str):
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/151 Safari/537.36",
            "Accept": "application/json,text/plain,*/*",
        },
    )
    with urllib.request.urlopen(req, timeout=25) as response:
        return json.loads(response.read().decode("utf-8", errors="replace"))


def fetch_character_directory():
    """Load the current MSF character names from Marvel Church and cache them locally."""
    cached = load_json(CHARACTER_CACHE_FILE, {})
    chars = cached.get("characters", []) if isinstance(cached, dict) else []
    if isinstance(chars, list) and len(chars) >= 100:
        return sorted({clean_text(str(x)) for x in chars if clean_text(str(x))}, key=str.casefold), "local character-directory cache"

    # Preferred path: use the site's WordPress REST API so character names can
    # be retrieved without scraping display markup.
    errors = []
    try:
        cats = fetch_json_url("https://www.marvel.church/wp-json/wp/v2/categories?slug=msf-characters&per_page=100")
        if not isinstance(cats, list) or not cats:
            raise RuntimeError("MSF Characters category was not returned by WordPress.")
        cat_id = int(cats[0]["id"])
        found = []
        page = 1
        while page <= 50:
            url = f"https://www.marvel.church/wp-json/wp/v2/posts?categories={cat_id}&per_page=100&page={page}&_fields=title,link"
            try:
                posts = fetch_json_url(url)
            except urllib.error.HTTPError as exc:
                if exc.code == 400 and page > 1:
                    break
                raise
            if not isinstance(posts, list) or not posts:
                break
            for post in posts:
                title = clean_text(re.sub(r"<[^>]+>", "", str((post.get("title") or {}).get("rendered", ""))))
                if title:
                    found.append(title)
            if len(posts) < 100:
                break
            page += 1
        found = sorted(set(found), key=str.casefold)
        if len(found) < 100:
            raise RuntimeError(f"Only found {len(found)} character entries through WordPress.")
        CHARACTER_CACHE_FILE.write_text(json.dumps({"characters": found}, indent=2, ensure_ascii=False), encoding="utf-8")
        return found, "live Marvel Church character directory"
    except Exception as exc:
        errors.append(f"WordPress: {exc}")

    # If WordPress REST is unavailable, use Playwright to collect visible
    # character-card titles from the paged Characters archive.
    try:
        from playwright.sync_api import sync_playwright
        found = []
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            try:
                page = browser.new_page(
                    viewport={"width": 1280, "height": 900},
                    user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151 Safari/537.36",
                )
                for n in range(1, 51):
                    url = "https://www.marvel.church/marvel-strike-force/msf-characters/" if n == 1 else f"https://www.marvel.church/marvel-strike-force/msf-characters/page/{n}/"
                    response = page.goto(url, wait_until="domcontentloaded", timeout=45000)
                    if response and response.status >= 400:
                        break
                    titles = page.locator("article .entry-title a, article h2 a, article h3 a").all_inner_texts()
                    titles = [clean_text(x) for x in titles if clean_text(x)]
                    before = len(found)
                    found.extend(titles)
                    if not titles or (n > 1 and len(found) == before):
                        break
            finally:
                browser.close()
        found = sorted(set(found), key=str.casefold)
        if len(found) < 100:
            raise RuntimeError(f"Only found {len(found)} character entries in the archive.")
        CHARACTER_CACHE_FILE.write_text(json.dumps({"characters": found}, indent=2, ensure_ascii=False), encoding="utf-8")
        return found, "live Marvel Church character directory (Chromium)"
    except Exception as exc:
        errors.append(f"Chromium: {exc}")

    raise RuntimeError("; ".join(errors))

def get_roster(team: str):
    directory = load_json(DIRECTORY_FILE, {})
    url = directory.get(team)
    if not url:
        raise ValueError("Unknown team template.")
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in {"www.marvel.church", "marvel.church"}:
        raise ValueError("Team URL is not a Marvel Church URL.")

    cache = load_json(CACHE_FILE, {})
    cached = cache.get(team.casefold(), {})
    members = cached.get("members", []) if isinstance(cached, dict) else []
    if isinstance(members, list) and len(members) == 5:
        return [str(x) for x in members], "local team-roster cache"

    errors = []
    html = None
    source = None
    try:
        html = fetch_with_urllib(url)
        source = "live Marvel Church Team Breakdown"
    except Exception as exc:
        errors.append(f"HTTPS: {exc}")

    if html is None:
        try:
            html = fetch_with_playwright(url)
            source = "live Marvel Church Team Breakdown (Chromium)"
        except Exception as exc:
            errors.append(f"Chromium: {exc}")

    if html is None:
        raise RuntimeError("; ".join(errors))

    members = parse_team_members(html)
    cache[team.casefold()] = {"team": team, "url": url, "members": members}
    save_cache(cache)
    return members, source


class Handler(SimpleHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/characters":
            try:
                characters, source = fetch_character_directory()
                self.send_json(200, {"characters": characters, "source": source})
            except Exception as exc:
                self.send_json(502, {"error": str(exc)})
            return
        if parsed.path == "/api/team-roster":
            params = urllib.parse.parse_qs(parsed.query)
            team = clean_text((params.get("team") or [""])[0])
            try:
                if not team:
                    raise ValueError("Missing team name.")
                members, source = get_roster(team)
                self.send_json(200, {"team": team, "members": members, "source": source})
            except Exception as exc:
                self.send_json(502, {"error": str(exc)})
            return
        super().do_GET()

    def send_json(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    os.chdir(ROOT)
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"MSF Attack Planner Web v0.2.4 running at http://localhost:{PORT}")
    print("Press Control-C to stop it.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        server.server_close()
