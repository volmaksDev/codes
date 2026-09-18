import argparse
import json
import logging
import re
import sys

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

FANDOM_API = "https://bloxfruits.fandom.com/api.php"
THG_URL = "https://tryhardguides.com/blox-fruits-codes/"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/json;q=0.9,*/*;q=0.8",
}

SKIP = {"code", "codes", "none", "n/a", "expired", "active", "new", "example"}
CODE_RE = re.compile(r"^[A-Za-z0-9_]{3,30}$")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("scraper")


def make_session() -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=4,
        backoff_factor=2,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset(["GET"]),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update(HEADERS)
    return session


def looks_like_code(text: str) -> bool:
    text = text.strip().strip("`:*'\"")
    return bool(CODE_RE.match(text)) and text.lower() not in SKIP


def fetch_fandom(session: requests.Session, debug: bool) -> dict | None:
    log.info("[fandom] requesting MediaWiki API...")
    resp = session.get(
        FANDOM_API,
        params={
            "action": "parse",
            "page": "Codes",
            "prop": "text",
            "format": "json",
            "formatversion": 2,
            "redirects": 1,
        },
        timeout=(10, 30),
    )
    resp.raise_for_status()
    raw = resp.json().get("parse", {}).get("text")
    if not raw:
        log.warning("[fandom] empty API response")
        return None
    if debug:
        open("debug_fandom.html", "w", encoding="utf-8").write(raw)

    active, expired, seen = [], [], set()
    section = active
    for el in BeautifulSoup(raw, "html.parser").find_all(["h2", "h3", "code"]):
        if el.name in ("h2", "h3"):
            heading = el.get_text(" ", strip=True).lower()
            section = expired if ("expire" in heading or "inactive" in heading) else active
            continue
        code = el.get_text(strip=True)
        if looks_like_code(code) and code not in seen:
            seen.add(code)
            section.append(code)

    log.info("[fandom] active: %d, expired: %d", len(active), len(expired))
    return {"active": active, "expired": expired} if active or expired else None


def fetch_thg(session: requests.Session, debug: bool) -> dict | None:
    log.info("[tryhardguides] fetching page...")
    resp = session.get(THG_URL, timeout=(10, 30))
    resp.raise_for_status()
    html = resp.text
    if debug:
        open("debug_thg.html", "w", encoding="utf-8").write(html)

    soup = BeautifulSoup(html, "html.parser")
    article = soup.select_one("article") or soup.select_one("main") or soup.body

    active, expired, seen = [], [], set()
    section = None
    for el in article.find_all(["h2", "h3", "h4", "li"]):
        if el.name in ("h2", "h3", "h4"):
            heading = el.get_text(" ", strip=True).lower()
            if "expire" in heading:
                section = expired
            elif "working" in heading or "active" in heading:
                section = active
            continue
        if section is None:
            continue
        text = el.get_text(" ", strip=True)
        first = re.split(r"\s+[—–:|]\s*", text, maxsplit=1)[0].strip(" `*'\"")
        if looks_like_code(first) and first not in seen:
            seen.add(first)
            section.append(first)

    log.info("[tryhardguides] active: %d, expired: %d", len(active), len(expired))
    return {"active": active, "expired": expired} if active or expired else None


def save(data: dict) -> None:
    with open("codes.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    log.info("Saved codes.json")


SOURCES = [
    ("fandom", fetch_fandom),
    ("tryhardguides", fetch_thg),
]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--debug", action="store_true",
                        help="save raw responses to debug_*.html")
    args = parser.parse_args()

    session = make_session()
    data = None

    for name, fetch in SOURCES:
        try:
            result = fetch(session, args.debug)
        except Exception as e:
            log.error("[%s] error: %s", name, e)
            result = None

        if result:
            data = result
            break
        log.warning("[%s] no codes found, trying next source...", name)

    if data is None:
        log.error("All sources failed")
        return 1

    save(data)
    return 0


if __name__ == "__main__":
    sys.exit(main())
