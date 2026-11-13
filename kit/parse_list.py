import re,html,json,sys
def parse(s):
    parts=re.split(r'<div class="js-item-product ',s)[1:]
    out=[]
    for p in parts:
        pid=re.search(r'data-product-id="(\d+)"',p)
        dv=re.search(r'data-variants="([^"]*)"',p)
        url=re.search(r'href="(https://(?:www\.)?mummaindumentaria\.com\.ar/productos/[^"]+)"',p)
        name=re.search(r'class="js-item-name[^"]*"[^>]*>\s*([^<]+?)\s*<',p) or re.search(r'title="([^"]+)"',p)
        out.append(dict(id=pid and pid.group(1), name=name and html.unescape(name.group(1)), url=url and url.group(1),
            variants=json.loads(html.unescape(dv.group(1))) if dv else None))
    return out
if __name__=='__main__':
    r=parse(open(sys.argv[1],encoding='utf-8').read())
    print(len(r), sum(1 for x in r if x['variants'] is None))
    for x in r[:4]: print(x['id'],x['name'],x['url'],len(x['variants'] or []), (x['variants'] or [{}])[0].get('option0'),(x['variants'] or [{}])[0].get('option1'))
