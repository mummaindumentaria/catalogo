"""Genera todos los catálogos de Mumma a partir de los datos relevados de la tienda."""
import json, sys, math, os, re, io, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gen
from PIL import Image, ImageFilter, ImageStat

R = gen.ROOT
OUT = f'{R}/out/catalogos'
os.makedirs(OUT, exist_ok=True)
d = json.load(open(f'{R}/cat/crawl.json'))
subs = json.load(open(f'{R}/cat/acc_subs.json'))
alb_codes = json.load(open(f'{R}/cat/album_codes.json'))
cat_photo = json.load(open(f'{R}/cat/cat_photo.json'))
P = {x['id']: x for x in d['productos']}
N = {i: gen.normalize(x) for i, x in P.items()}

ROPA = [('Remeras', 'remeras'), ('Camisas & Blusas', 'camisas-blusas'), ('Sweaters & Poleras', 'sweaters-poleras'),
        ('Buzos', 'buzos'), ('Joggers & Pantalones', 'joggers-pantalones'), ('Blazers & Chalecos', 'blazers-chalecos'),
        ('Shorts & Polleras', 'shorts-polleras'), ('Vestidos', 'vestidos')]
LIQ = ('Liquidación', 'liquidacion')
ACC = [('Gorros', 'gorros'), ('Pashminas', 'pashminas'), ('Carteras', 'carteras'), ('Cinturones', 'cinturones'),
       ('Bijou', 'bijou'), ('Lentes', 'lentes'), ('Abanicos & Complementos', 'abanicos-lentes-y-complementos')]

# códigos: el del álbum si existe, si no el de la web
CODES = {i: alb_codes.get(i) or n['sku'] for i, n in N.items()}

# --- membresía de categorías ---
cat_ids = {slug: [x['id'] for x in d[slug]] for _, slug in ROPA + [LIQ] + [('Valijas', 'valijas')]}
liq_set = set(cat_ids['liquidacion'])
main = [s for _, s in ROPA] + ['accesorios', 'valijas']
in_main = {x['id'] for s in main for x in d[s]}
# accesorios por subcategoría (sin repetir) + gorros sin categoría + otros
acc_ids = {}
seen = set()
for _, s in ACC:
    acc_ids[s] = [x['id'] for x in subs[s] if x['id'] not in seen]
    seen |= set(acc_ids[s])
orphans = [x['id'] for x in d['productos'] if x['id'] not in in_main]
acc_ids['gorros'] += [i for i in orphans if i not in seen]
seen |= set(orphans)
_rest = [x['id'] for x in d['accesorios'] if x['id'] not in seen]
_gorro = re.compile(r'(?i)gorr|beanie|boina|visera|sombrero')
acc_ids['gorros'] += [i for i in _rest if _gorro.search(P[i]['name'])]
acc_ids['otros-accesorios'] = [i for i in _rest if not _gorro.search(P[i]['name'])]
ACC_ALL = ACC + [('Otros accesorios', 'otros-accesorios')]


def sharp_pick(ids):
    """Foto más nítida entre las principales de la categoría (para categorías sin elección manual)."""
    best = (-1, ids[0])
    for i in ids[:40]:
        f = gen.local_img(N[i], w=1024, big=True)
        im = Image.open(f).convert('L'); w, h = im.size
        sm = im.resize((500, int(500 * h / w)))
        s = ImageStat.Stat(sm.filter(ImageFilter.FIND_EDGES)).var[0]
        best = max(best, (s, i))
    return best[1]


def photo_for(slug, ids):
    pid = cat_photo.get(slug)
    if pid not in N or pid not in ids:  # si la foto elegida se agotó, elige la más nítida de la categoría
        pid = sharp_pick(ids)
    return gen.local_img(N[pid], w=1024, big=True)


OFFER_PHOTOS = [f'{R}/img/offer_{k}.jpg' for k in (4, 19, 66, 81)]  # fotos del álbum de ofertas (fijas)


REM_SUBS = [('Lisas', 'lisas'), ('Estampadas', 'estampadas'), ('Musculosas', 'musculosas'), ('Bodys & Tops', 'bodys-tops')]
_rem = json.load(open(f'{R}/cat/rem_subs.json'))


LIGHT = {'accesorios', 'liquidacion', 'valijas'} | {s for _, s in ACC_ALL}


def split_subs(slug, ids):
    """Subsecciones (Remeras y la sección Accesorios del completo): [(título, anchor, ids)]."""
    if slug == 'accesorios':
        idset, out = set(ids), []
        for t, s in ACC_ALL:
            sid = [i for i in acc_ids[s] if i in idset]
            if sid: out.append((t, f'sub-acc-{s}', sid))
        return out
    if slug != 'remeras': return None
    out, used = [], set()
    for t, s in REM_SUBS:
        sid = [i for i in ids if i in set(_rem.get(s, [])) and i not in used]; used |= set(sid)
        if sid: out.append((t, f'sub-remeras-{s}', sid))
    rest = [i for i in ids if i not in used]
    if rest: out.append(('Otras', 'sub-remeras-otras', rest))
    return out


def plan_section(slug, ids):
    """Cantidad de páginas y página relativa de inicio de cada subsección."""
    n = 1 + (1 if slug == 'remeras' else 0)
    subs = split_subs(slug, ids)
    starts = []
    for t, a, sid in (subs or [(None, None, ids)]):
        starts.append(n); n += math.ceil(len(sid) / 4)
    return n, subs, starts


def section(title, slug, ids, start, web_slug, nxt):
    n, subs, starts = plan_section(slug, ids)
    sub_info = [dict(title=t, anchor=a, count=len(sid), page=start + st) for (t, a, sid), st in zip(subs, starts)] if subs else None
    gen.CARD_W = (300 if slug in LIGHT else 420) if os.environ.get('MUMMA_LIVIANO') else (460 if slug in LIGHT else 640)
    gen.THUMBS = True
    pages = [gen.page_category(title, web_slug or slug, len(ids), photo_for(slug, ids), 'cat-' + slug, start, sub_info)]
    pg = start + 1
    if slug == 'remeras':
        pages.append(gen.page_offer(OFFER_PHOTOS, pg)); pg += 1
    groups = [(f'{title} · {t}', a, sid) for t, a, sid in subs] if subs else [(title, None, ids)]
    for gi, (gt, ga, sid) in enumerate(groups):
        prods = [N[i] for i in sid]
        for k in range(0, len(prods), 4):
            last = gi == len(groups) - 1 and k + 4 >= len(prods)
            mid = nxt if last else ''
            pages.append(gen.page_products(gt, prods[k:k + 4], CODES, pg, ga if k == 0 else None, mid)); pg += 1
    return pages, pg, sub_info


def build(name, sub, secs, with_index):
    """secs: lista de (title, slug, ids, web_slug)."""
    gen.HOME, gen.HOME_LABEL, gen.HOME_ICON = ('indice', 'Índice', gen.ICON_LIST) if with_index else ('inicio', 'Inicio', gen.ICON_UP)
    pages = [gen.page_cover(sub)]
    start = 4 if with_index else 3
    if with_index:
        entries, pg = [], start
        for t, s, ids, w in secs:
            entries.append(dict(title=t, anchor='cat-' + s, count=len(ids), page=pg, photo=photo_for(s, ids)))
            pg += plan_section(s, ids)[0]
        pages.append(gen.page_index(entries, 2, start - 1))
    pages.append(gen.page_info(start - 1))
    pg = start
    outline = [('Cómo comprar', 'como-comprar', [])]
    for k, (t, s, ids, w) in enumerate(secs):
        if k + 1 < len(secs):
            nxt = f'<a href="#cat-{secs[k+1][1]}">Siguiente: {gen.e(secs[k+1][0])} →</a>'
        else:
            nxt = f'<a href="#{gen.HOME}">Volver al {"índice" if with_index else "inicio"} ↑</a>'
        p, pg, sub_info = section(t, s, ids, pg, w, nxt)
        pages += p
        outline.append((t, 'cat-' + s, [(x['title'], x['anchor']) for x in (sub_info or [])]))
    out = f'{OUT}/{name}{" (liviano)" if os.environ.get("MUMMA_LIVIANO") else ""}.pdf'
    gen.render(pages, out, outline)
    return out, len(pages)


if __name__ == '__main__':
    only = sys.argv[1:]
    jobs = []
    # 1) completo: nuevos ingresos + ropa (cada producto una sola vez, liquidación aparte) + accesorios + liquidación
    used = set(liq_set); secs = []
    # nuevos ingresos: cat/new_ids.json si existe (lo arma la tarea con la fecha de carga de Tiendanube);
    # si no, se estiman por el id del producto (los ids de Tiendanube crecen con la fecha de carga).
    _nf = f'{R}/cat/new_ids.json'
    if os.path.exists(_nf):
        new_ids = [i for i in json.load(open(_nf)) if i in P and i not in liq_set]
    else:
        new_ids = []
    new_ids.sort(key=lambda i: -int(i))
    gen.NEW = set(new_ids)
    if new_ids: secs.append(('Nuevos ingresos', 'nuevos', new_ids, 'productos/?sort_by=created-descending'))
    for t, s in ROPA:
        ids = [i for i in cat_ids[s] if i not in used]; used |= set(ids); secs.append((t, s, ids, None))
    acc_flat = [i for t, s in ACC_ALL for i in acc_ids[s] if i not in liq_set]
    secs.append(('Accesorios', 'accesorios', acc_flat, None))
    secs.append((LIQ[0], LIQ[1], cat_ids['liquidacion'], None))
    jobs.append(('Mumma - Catalogo Completo', 'mayorista', secs, True))
    # 2) uno por categoría de ropa + liquidación
    for t, s in ROPA + [LIQ]:
        jobs.append((f'Mumma - {t.replace("&", "y")}', 'mayorista', [(t, s, cat_ids[s], None)], False))
    # 3) accesorios por subcategoría
    acc_secs = [(t, s, acc_ids[s], 'accesorios/' + s if s != 'otros-accesorios' else 'accesorios') for t, s in ACC_ALL if acc_ids[s]]
    jobs.append(('Mumma - Accesorios', 'mayorista · accesorios', acc_secs, True))
    # 4) valijas
    jobs.append(('Mumma - Valijas', 'mayorista · valijas', [('Valijas', 'valijas', cat_ids['valijas'], None)], False))
    for name, sub, secs, idx in jobs:
        if only and not any(o.lower() in name.lower() for o in only): continue
        out, n = build(name, sub, secs, idx)
        print(f'{name}: {n} págs, {os.path.getsize(out)/1e6:.1f} MB', flush=True)
