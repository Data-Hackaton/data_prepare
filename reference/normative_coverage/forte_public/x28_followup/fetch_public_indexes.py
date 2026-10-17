"""Archive public index pages used in the focused X-28 source search."""
import hashlib
import json
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import quote, urljoin, urlsplit
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent / "discovery"
PAGES = {
    "esg": "https://forte.kz/ru/esg",
    "cybersecurity": "https://forte.kz/ru/cybersecurity",
    "information": "https://forte.kz/ru/information",
    "procurement_rules_landing": "https://forte.kz/inform/21-11-2023",
    "procurement_consulting": "https://mp.kz/tender/233749-Консалтинговые услуги по ИБ (информационной безопасности)",
    "forte_robots": "https://forte.kz/robots.txt",
    "forte_sitemap": "https://forte.kz/sitemap.xml",
}


class PublicLinks(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.current = None

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self.current = {"url": dict(attrs).get("href", ""), "text": ""}

    def handle_data(self, data):
        if self.current is not None:
            self.current["text"] += data

    def handle_endtag(self, tag):
        if tag == "a" and self.current is not None:
            self.current["text"] = " ".join(self.current["text"].split())
            self.links.append(self.current)
            self.current = None


def fetch(slug, url):
    if urlsplit(url).hostname not in {"mp.kz", "forte.kz", "bank.forte.kz", "ir.forte.kz"}:
        raise ValueError("Unexpected source host")
    ROOT.mkdir(parents=True, exist_ok=True)
    output = ROOT / (slug + ".json")
    if output.exists():
        return json.loads(output.read_text(encoding="utf-8"))
    encoded_url = quote(url, safe=":/?=&%#-._~()")
    record = {"url": encoded_url, "checked_at_utc": datetime.now(timezone.utc).isoformat()}
    try:
        with urlopen(Request(encoded_url, headers={"User-Agent": "Mozilla/5.0"}), timeout=30) as response:
            raw = response.read(8_000_001)
            if len(raw) > 8_000_000:
                raise ValueError("Unexpectedly large index page")
            record.update(final_url=response.url, status=response.status,
                          content_type=response.headers.get("Content-Type"))
        record["sha256"] = hashlib.sha256(raw).hexdigest()
        (ROOT / (slug + ".html")).write_bytes(raw)
        parser = PublicLinks()
        parser.feed(raw.decode("utf-8", errors="replace"))
        for link in parser.links:
            link["url"] = urljoin(record["final_url"], link["url"])
        record["links"] = parser.links
    except Exception as exc:
        record["error"] = f"{type(exc).__name__}: {exc}"
    output.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    return record


if __name__ == "__main__":
    for name, address in PAGES.items():
        result = fetch(name, address)
        print(json.dumps({"name": name, "status": result.get("status"),
                          "error": result.get("error"),
                          "links": [r for r in result.get("links", [])
                                    if any(s in r["url"].lower() + r["text"].lower()
                                           for s in ["forte", "документ", "pdf", "docx"])]},
                         ensure_ascii=False), flush=True)
