"""Lossless-text normalization of official HTML; no legal conclusions inferred."""
from collections import Counter
from pathlib import Path
from urllib.parse import urljoin
import hashlib
import json
import re
import sys
from lxml import html, etree

ROOT = Path(__file__).resolve().parent
OUT = ROOT/'parsed'

def clean(value):
    return ' '.join(value.split())

def txt(node):
    return clean(' '.join(node.itertext()))

def compact(value):
    return re.sub(r'\s+', '', value)

def normalize(meta):
    ident = meta['id']
    raw = (ROOT/'sources'/(ident+'.html')).read_bytes()
    tree = html.fromstring(raw.decode('utf-8'))
    articles = tree.xpath('//article')
    assert len(articles) == 1, (ident, len(articles))
    article = articles[0]
    blocks, headings = [], []
    context, article_number = '', None
    used = Counter()

    def add(text, node=None):
        nonlocal context, article_number
        tag = node.tag.lower() if node is not None and isinstance(node.tag,str) else 'text'
        anchor = node.get('id') if node is not None else None
        is_heading = bool(re.fullmatch(r'h[1-6]',tag))
        am = re.match(r'^Статья\s+(\d+(?:-\d+)?)\.', text)
        if am:
            article_number = am[1]
            is_heading = True
        kind = 'heading' if is_heading else 'table' if tag=='table' else 'paragraph'
        if is_heading:
            context = text
        elif text.startswith(('Сноска.', 'Примечание')):
            kind = 'note'
        pm = re.match(r'^[«"“]?(\d+(?:[-–]\d+)?)\.\s',text)
        sm = re.match(r'^[«"“]?(\d+(?:[-–]\d+)?)\)\s',text)
        if tag in ('p','text') and pm:
            kind = 'point'
        elif tag in ('p','text') and sm:
            kind = 'subpoint'
        key = ident+':'+(anchor or f'block-{len(blocks)+1}')
        used[key]+=1
        if used[key]>1:
            key += f':occurrence-{used[key]}'
        b = {'id':key,'order':len(blocks)+1,'anchor':anchor,'tag':tag,'kind':kind,
             'heading':context,'article_number':article_number,'text':text,
             'point':pm[1] if kind=='point' else None,
             'subpoint':sm[1] if kind=='subpoint' else None,
             'url':meta['page_url']+('#'+anchor if anchor else '')}
        if node is not None:
            b['anchors'] = [n.get('id') for n in node.iter() if isinstance(n.tag,str) and n.get('id')]
            b['links'] = [{'text':txt(n),'url':urljoin(meta['page_url'],n.get('href'))}
                          for n in node.iter('a') if n.get('href') and not n.get('href').startswith('javascript:')]
            b['images'] = [{'src':urljoin(meta['page_url'],n.get('src')),'alt':n.get('alt','')}
                           for n in node.iter('img') if n.get('src')]
            if kind=='table':
                b['rows'] = [[{'text':txt(c),'rowspan':int(c.get('rowspan','1')),
                              'colspan':int(c.get('colspan','1'))}
                             for c in row.xpath('./th|./td')] for row in node.xpath('.//tr')]
                b['html'] = etree.tostring(node,method='html',encoding='unicode',with_tail=False)
        blocks.append(b)
        if is_heading:
            headings.append({'order':b['order'],'anchor':anchor,'text':text,'article_number':article_number})

    if clean(article.text or ''):
        add(clean(article.text))
    for node in article:
        if isinstance(node.tag,str):
            value = txt(node)
            if value or node.xpath('.//img') or node.tag=='img':
                add(value,node)
        if clean(node.tail or ''):
            add(clean(node.tail))
    full = '\n'.join(b['text'] for b in blocks)
    original = txt(article)
    assert compact(full)==compact(original), ident
    units, current = [], None
    for b in blocks:
        if b['kind']=='point':
            current = {k:b[k] for k in ('id','anchor','point','heading','article_number','url','text')}
            current.update({'document_id':ident,'start_block':b['order'],'end_block':b['order']})
            units.append(current)
        elif b['kind']=='heading' or (b['kind']=='table' and re.match(r'^(Приложени[ея]|Утвержден)',b['text'])):
            current = None
        elif current:
            current['text'] += '\n'+b['text']
            current['end_block'] = b['order']
    result = {'metadata':meta,'text_coverage_complete':True,'source_sha256':hashlib.sha256(raw).hexdigest(),
              'nonwhitespace_characters':len(compact(full)), 'blocks':blocks,
              'headings':headings,'units':units,'stats':dict(Counter(b['kind'] for b in blocks))}
    (OUT/(ident+'.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    (OUT/(ident+'.txt')).write_text(meta['title']+'\n'+meta['page_url']+'\n\n'+full+'\n',encoding='utf-8')
    md=['# '+meta['title'],'',meta['official_name'] or '', '', '[Официальный источник]('+meta['page_url']+')','']
    for b in blocks:
        md += [('## ' if b['kind']=='heading' else '')+b['text'],'']
    (OUT/(ident+'.md')).write_text('\n'.join(md),encoding='utf-8')
    return {'id':ident,'title':meta['title'],'blocks':len(blocks),'tables':result['stats'].get('table',0),
            'units':len(units),'text_coverage_complete':True,'source_sha256':result['source_sha256']}

if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    OUT.mkdir(exist_ok=True)
    manifest=json.loads((ROOT/'source_manifest.json').read_text(encoding='utf-8'))
    result=[normalize(meta) for meta in manifest if meta['status']=='downloaded']
    (ROOT/'parsing_manifest.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2))
