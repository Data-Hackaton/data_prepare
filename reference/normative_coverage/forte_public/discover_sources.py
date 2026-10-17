"""Archive official ForteBank document indexes and enumerate public links."""
import hashlib
import json
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent / 'discovery'
PAGES = {
    'forte_documents': 'https://forte.kz/ru/documents',
    'business_documents': 'https://business.forte.kz/ru/documents',
    'reporting': 'https://forte.kz/ru/reporting',
    'compliance': 'https://bank.forte.kz/ru/Compliance',
    'business_service': 'https://business.forte.kz/ru/service',
    'retail_cards': 'https://bank.forte.kz/ru/cards',
    'investors': 'https://ir.forte.kz/',
    'certification': 'https://forte.kz/ru/certification-center',
}


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows = []
        self.current = None

    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            self.current = {'text': '', 'url': dict(attrs).get('href', '')}

    def handle_data(self, data):
        if self.current is not None:
            self.current['text'] += data

    def handle_endtag(self, tag):
        if tag == 'a' and self.current is not None:
            self.current['text'] = ' '.join(self.current['text'].split())
            self.rows.append(self.current)
            self.current = None


def main():
    ROOT.mkdir(exist_ok=True)
    for slug, url in PAGES.items():
        if (ROOT / (slug + '.links.json')).exists():
            continue
        request = Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urlopen(request, timeout=40) as response:
            data = response.read()
            final_url = response.url
        (ROOT / (slug + '.html')).write_bytes(data)
        parser = Links()
        parser.feed(data.decode('utf-8'))
        for row in parser.rows:
            row['url'] = urljoin(final_url, row['url'])
        result = {
            'url': url, 'final_url': final_url,
            'retrieved_at_utc': datetime.now(timezone.utc).isoformat(),
            'sha256': hashlib.sha256(data).hexdigest(),
            'links': parser.rows,
        }
        (ROOT / (slug + '.links.json')).write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
        useful = [r for r in parser.rows if any(t in r['url'].lower()
                  for t in ['.pdf', '.doc', 'sustain', 'report', 'privac', 'secur', 'esg'])]
        print(json.dumps({'page': url, 'links': useful}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
