"""Generador de catálogos Mumma: datos de la tienda -> HTML -> PDF (Chrome headless) + marcadores."""
import json, os, re, io, subprocess, html, datetime, urllib.parse
from PIL import Image

ROOT = os.path.dirname(os.path.abspath(__file__))
FECHA = datetime.date.today().strftime('%d/%m/%Y')
BASE = 'https://www.mummaindumentaria.com.ar'
WA_ORDER = '5491128259705'  # número que recibe las consultas desde las fichas
ICON_LIST = '<svg viewBox="0 0 24 24" width="100%" height="100%" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"><path d="M8 6.5h12M8 12h12M8 17.5h12"/><circle cx="4" cy="6.5" r=".9" fill="currentColor"/><circle cx="4" cy="12" r=".9" fill="currentColor"/><circle cx="4" cy="17.5" r=".9" fill="currentColor"/></svg>'
ICON_UP = '<svg viewBox="0 0 24 24" width="100%" height="100%" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M12 19V5M5.5 11.5 12 5l6.5 6.5"/></svg>'
ICON_WA = '<svg viewBox="0 0 24 24" width="100%" height="100%" fill="currentColor"><path d="M12 2.2A9.7 9.7 0 0 0 3.7 16.9L2.3 21.8l5-1.3A9.7 9.7 0 1 0 12 2.2Zm0 17.7c-1.5 0-2.9-.4-4.2-1.1l-.3-.2-3 .8.8-2.9-.2-.3A8 8 0 1 1 12 19.9Zm4.4-6c-.2-.1-1.4-.7-1.7-.8-.2-.1-.4-.1-.5.1l-.8 1c-.1.2-.3.2-.5.1a6.6 6.6 0 0 1-3.3-2.9c-.2-.4.2-.4.7-1.3.1-.2 0-.3 0-.4l-.8-1.8c-.2-.5-.4-.4-.5-.4h-.5a.9.9 0 0 0-.7.3c-.2.3-.9.9-.9 2.2s.9 2.5 1 2.7c.1.2 1.8 2.8 4.5 3.9 1.7.7 2.3.8 3.2.6.5-.1 1.4-.6 1.7-1.2.2-.6.2-1.1.1-1.2l-.5-.3Z"/></svg>'
ICON_IG = '<svg viewBox="0 0 24 24" width="100%" height="100%" fill="none" stroke="currentColor" stroke-width="1.7"><rect x="3.5" y="3.5" width="17" height="17" rx="4.5"/><circle cx="12" cy="12" r="4"/><circle cx="17.2" cy="6.8" r=".9" fill="currentColor" stroke="none"/></svg>'
ICON_TT = '<svg viewBox="0 0 24 24" width="100%" height="100%" fill="currentColor"><path d="M16.6 3c.3 2.2 1.6 3.6 3.9 3.8v3a7 7 0 0 1-3.9-1.2v6.3A5.9 5.9 0 1 1 10.7 9v3.1a2.9 2.9 0 1 0 2.9 2.8V3h3Z"/></svg>'
HOME, HOME_LABEL, HOME_ICON = 'indice', 'Índice', ICON_LIST
CARD_W = 640
THUMBS = False  # columna de miniaturas de colores (solo ropa)
NEW = set()  # productos cargados en los últimos 15 días
PRICE_OVERRIDE = {10000: 9999}  # vestidos en oferta: precio confirmado por Tomi

SIZES = {'XXS', 'XS', 'S', 'M', 'L', 'XL', 'XXL', 'XXXL', 'U', 'UNICO', 'ÚNICO', 'TALLE UNICO', 'TALLE ÚNICO',
         'S/M', 'M/L', 'L/XL', 'XL/XXL', '1', '2', '3', '4', '5', '6'} | {str(n) for n in range(24, 60)}
SIZE_ORDER = ['XXS', 'XS', 'S', 'S/M', 'M', 'M/L', 'L', 'L/XL', 'XL', 'XL/XXL', 'XXL', 'XXXL']
e = html.escape


def is_size(v):
    return v is not None and v.strip().upper() in SIZES


def size_key(s):
    u = s.upper()
    if u in SIZE_ORDER: return (0, SIZE_ORDER.index(u))
    if u.isdigit(): return (1, int(u))
    return (2, 0)


def fmt(n):
    return '$' + f'{int(round(n)):,}'.replace(',', '.')


def normalize(x):
    vs = [v for v in x['variants'] if v.get('available') and (v.get('stock') is None or v['stock'] > 0)]
    colors, sizes = [], []
    for v in vs:
        for k in ('option0', 'option1', 'option2'):
            val = v.get(k)
            if not val: continue
            tgt = sizes if is_size(val) else colors
            if val not in tgt: tgt.append(val)
    sizes.sort(key=size_key)
    prices = sorted({PRICE_OVERRIDE.get(v['price_number'], v['price_number']) for v in vs})
    comp = sorted({v['compare_at_price_number'] for v in vs if v.get('compare_at_price_number')})
    skus = {(v.get('sku') or '').split('-')[0].strip() for v in vs if v.get('sku')}
    img = next((v['image_url'] for v in vs if v.get('image_url')), None) or x['variants'][0].get('image_url')
    cimgs = {}
    for v in vs:
        col = next((v.get(k) for k in ('option0', 'option1', 'option2') if v.get(k) and not is_size(v.get(k))), None)
        u = v.get('image_url')
        if col and u and col not in cimgs and u not in cimgs.values(): cimgs[col] = u
    slug = x['url'].split('/productos/')[1].split('?')[0].strip('/')
    return dict(id=x['id'], name=x['name'], colors=colors, sizes=sizes, price=prices[0], price_max=prices[-1],
                compare=comp[-1] if comp else None, sku=sorted(skus)[0] if len(skus) == 1 else None,
                img='https:' + img if img and img.startswith('//') else img, url=f'{BASE}/productos/{slug}/',
                color_imgs=list(cimgs.values()))


def local_img(p, w=640, big=False, q=78):
    os.makedirs(f'{ROOT}/img/cat', exist_ok=True)
    f = f'{ROOT}/img/cat/{p["id"]}_{w}.jpg'
    if not os.path.exists(f):
        u = re.sub(r'-\d+-\d+\.webp$', '-1024-1024.webp', p['img'])
        b = subprocess.run(['curl', '-sSL', '--max-time', '40', '--retry', '2', u], capture_output=True).stdout
        im = Image.open(io.BytesIO(b)).convert('RGB')
        im.thumbnail((w, int(w * 4 / 3) + 10))
        im.save(f, 'JPEG', quality=q, optimize=True, progressive=True)
    return f


def thumb(url):
    os.makedirs(f'{ROOT}/img/th', exist_ok=True)
    tw = 150 if CARD_W >= 640 else (110 if CARD_W >= 460 else 90)  # miniaturas más livianas en accesorios, liquidación y versión liviana
    f = f"{ROOT}/img/th/{re.sub(r'[^A-Za-z0-9]', '', url)[-56:]}_{tw}.jpg"
    if not os.path.exists(f):
        u = re.sub(r'-\d+-\d+\.webp$', '-480-0.webp', 'https:' + url if url.startswith('//') else url)
        b = subprocess.run(['curl', '-sSL', '--max-time', '30', '--retry', '2', u], capture_output=True).stdout
        try:
            im = Image.open(io.BytesIO(b)).convert('RGB')
        except Exception:
            # algunas fotos no tienen la versión chica: probar con la original, y si falla, saltear la miniatura
            b = subprocess.run(['curl', '-sSL', '--max-time', '30', '--retry', '2', re.sub(r'-480-0\.webp$', '-1024-1024.webp', u)], capture_output=True).stdout
            try: im = Image.open(io.BytesIO(b)).convert('RGB')
            except Exception: return None
        im.thumbnail((tw, int(tw * 4 / 3)))
        im.save(f, 'JPEG', quality=72 if tw >= 150 else (66 if tw >= 110 else 60), optimize=True)
    return f


_TH_CACHE = {}


def thumbs_html(p):
    k = (p['id'], CARD_W)
    if k not in _TH_CACHE: _TH_CACHE[k] = _thumbs_html(p)
    return _TH_CACHE[k]


def _thumbs_html(p):
    ci = p.get('color_imgs') or []
    if not THUMBS or len(ci) < 2: return ''
    files = [f for f in (thumb(u) for u in ci) if f]
    if len(files) < 2: return ''
    show, extra = files[:5], len(files) - 5
    th = ''.join(f'<span class="th"><img src="file://{f}"></span>' for f in show)
    if extra > 0: th += f'<span class="th more">+{extra}</span>'
    return f'<div class="ths">{th}</div>'


# ---------- piezas comunes ----------
def hdr(sec):
    return (f'<header><a class="home" href="#{HOME}"><img class="m" src="file://{ROOT}/brand/m_bordo.png">'
            f'<span class="pill"><i>{HOME_ICON}</i>{HOME_LABEL}</span></a><span class="sec">{e(sec)}</span></header>')


def ftr(pageno, mid=''):
    return f'<footer><span>Precios válidos al {FECHA}</span><span class="fm">{mid}</span><span>{pageno}</span></footer>'


def wa_link(text):
    return f'https://wa.me/{WA_ORDER}?text=' + urllib.parse.quote(text)


def card(p, code):
    price = fmt(p['price']) + ('' if p['price'] == p['price_max'] else ' – ' + fmt(p['price_max']))
    old = f'<span class="old">{fmt(p["compare"])}</span>' if p['compare'] and p['compare'] > p['price'] else ''
    off = f'<span class="tag">-{round(100 - p["price"] * 100 / p["compare"])}%</span>' if old else ''
    if p['id'] in NEW: off = '<span class="tag new">Nuevo</span>' + off.replace('class="tag"', 'class="tag t2"')
    cd = f'<div class="cd">Cód. {e(code)}</div>' if code else ''
    rows = ''
    if p['colors']: rows += f'<div class="row"><b>Colores</b> {e(" · ".join(p["colors"]))}</div>'
    if p['sizes']: rows += f'<div class="row"><b>Talles</b> {e(" · ".join(p["sizes"]))}</div>'
    msg = (f'¡Hola! Vi el catálogo de Mumma y me interesa:\n{p["name"]}' + (f' (Cód. {code})' if code else ''))
    return f'''<div class="card">
  <a href="{p['url']}"><div class="ph{' has-th' if thumbs_html(p) else ''}{' fit' if CARD_W < 640 else ''}"><img src="file://{local_img(p, w=CARD_W, q=78 if CARD_W >= 640 else (72 if CARD_W >= 460 else 66))}">{off}{thumbs_html(p)}</div></a>
  <div class="meta">
    <a href="{p['url']}"><div class="top"><div class="nm">{e(p['name'])}</div>{cd}</div>
    <div class="pr">{old}<span class="now">{price}</span></div></a>
    {rows}
    <a class="wab" href="{wa_link(msg)}"><i>{ICON_WA}</i>Consultar</a>
  </div>
</div>'''


CSS = open(f'{ROOT}/catalog.css').read().replace('{ROOT}', ROOT)


# ---------- páginas ----------
def page_products(title, prods, codes, pageno, anchor=None, mid=''):
    cards = ''.join(card(p, codes.get(p['id'])) for p in prods)
    aid = f' id="{anchor}"' if anchor else ''
    return f'''<section class="page prod"{aid}>
  {hdr(title)}
  <div class="grid">{cards}</div>
  {ftr(pageno, mid)}
</section>'''


def page_cover(sub):
    import cover_img
    bg = cover_img.build(sub)
    return f'''<section class="page cover" id="inicio">
  <div class="cv-photo" style="background-image:url('file://{bg}')"></div>
  <div class="cv-body"><div class="valid">Precios válidos al {FECHA}</div></div>
</section>'''


def page_index(entries, pageno, info_page=3):
    """Índice con fotos que ocupa toda la página: 3 columnas, alto de foto calculado según la cantidad de filas."""
    import math
    rows = math.ceil(len(entries) / 3)
    avail = 180.0  # mm útiles entre el encabezado y el pie
    ph = max(30.0, (avail - (rows - 1) * 3.5) / rows - 9.5)
    tiles = ''.join(f'''<a class="it" href="#{x['anchor']}">
  <div class="itp" style="height:{ph:.1f}mm"><img src="file://{x['photo']}"></div>
  <div class="itn">{e(x['title'])}</div><div class="itc">{x['count']} productos · pág. {x['page']}</div></a>''' for x in entries)
    return f'''<section class="page index" id="indice">
  {hdr('Índice')}
  <div class="igrid big">{tiles}</div>
  {ftr(pageno)}
</section>'''


def page_category(title, slug, count, photo, anchor, pageno, subs=None):
    sub_html, cls = '', ''
    if subs:
        cls = ' with-subs' + (' many-subs' if len(subs) > 5 else '')
        sub_html = '<div class="cp-subs">' + ''.join(
            f'<a class="ix" href="#{s["anchor"]}"><span class="ixn">{e(s["title"])}</span><span class="ixc">{s["count"]} productos</span><span class="ixd"></span><span class="ixp">{s["page"]}</span></a>'
            for s in subs) + '</div>'
    return f'''<section class="page catp{cls}" id="{anchor}">
  {hdr('Colección')}
  <div class="cp-t">{e(title)}</div>
  <div class="cp-c">{count} productos</div>
  <div class="cp-ph"><img src="file://{photo}"></div>
  {sub_html}
  <a class="cp-w" href="{BASE}/{slug}/">Ver categoría en la web →</a>
  {ftr(pageno)}
</section>'''


WA = [('+54 9 11 2825-9705', '5491128259705')]


def page_info(pageno=3):
    wa = ''.join(f'<a class="wa" href="https://wa.me/{n}">WhatsApp {t}</a>' for t, n in WA)
    return f'''<section class="page info" id="como-comprar">
  {hdr('Cómo comprar')}
  <h3>Descuentos por monto de compra</h3>
  <div class="tiers">
    <div class="t"><div class="p">10%</div><div class="d">desde<br>$150.000</div></div>
    <div class="t"><div class="p">15%</div><div class="d">desde<br>$500.000</div></div>
    <div class="t"><div class="p">20%</div><div class="d">desde<br>$1.000.000</div></div>
  </div>
  <div class="free">Envío gratis superando $1.000.000 · Sin mínimo de compra</div>
  <div class="cols">
    <div><h3>Dónde comprar</h3>
      <p>Online, con envío a todo el país o retiro en el local.</p>
      <p>Presencial en Av. Avellaneda 3185, Flores, CABA.</p></div>
    <div><h3>Horarios del local</h3>
      <p>Lunes a viernes de 8:30 a 17 h<br>Sábados de 8:30 a 14 h<br>Domingos cerrado</p></div>
  </div>
  <h3>Formas de pago</h3>
  <p>Efectivo · Transferencia · Débito · Crédito · Mercado Pago</p>
  <h3>Contacto</h3>
  <div class="was">{wa}</div>
  <div class="socials">
    <a class="soc" href="https://www.instagram.com/mummaindumentaria/"><i>{ICON_IG}</i><span>Instagram<b>@mummaindumentaria</b></span></a>
    <a class="soc" href="https://www.tiktok.com/@mummaindumentaria"><i>{ICON_TT}</i><span>TikTok<b>@mummaindumentaria</b></span></a>
  </div>
  <p><a href="mailto:mumma328@gmail.com">mumma328@gmail.com</a> · <a href="{BASE}">mummaindumentaria.com.ar</a></p>
  <p class="tip">En cada producto vas a encontrar el botón <b>Consultar</b>: te abre WhatsApp con el producto ya escrito.</p>
  <div class="warn">Nuestras únicas redes oficiales son las que figuran en este catálogo, siempre con el nombre Mumma Indumentaria. Cualquier otra cuenta con un nombre similar no somos nosotros.</div>
  {ftr(pageno)}
</section>'''


def page_offer(photos, pageno):
    tiers = [('1', '$6.999'), ('2', '$12.999'), ('4', '$24.999'), ('10', '$59.999')]
    t = ''.join(f'<div class="ot"><div class="oq">{q}<span>x</span></div><div class="op">{p}</div></div>' for q, p in tiers)
    ph = ''.join(f'<div class="oph"><img src="file://{f}"></div>' for f in photos)
    msg = '¡Hola! Vi el catálogo de Mumma y me interesa la oferta de remeras estampadas surtidas.'
    return f'''<section class="page offer">
  {hdr('Ofertas')}
  <div class="o-t">Remeras estampadas</div>
  <div class="o-s">Diseños surtidos</div>
  <div class="o-grid">{ph}</div>
  <div class="o-tiers">{t}</div>
  <a class="wab big" href="{wa_link(msg)}"><i>{ICON_WA}</i>Consultar esta oferta</a>
  <div class="o-note">Diseños y colores surtidos según stock.</div>
  {ftr(pageno)}
</section>'''


def render(pages, out_pdf, outline=None):
    h = f'<!doctype html><html lang="es"><head><meta charset="utf-8"><style>{CSS}</style></head><body>{"".join(pages)}</body></html>'
    hp = out_pdf.replace('.pdf', '.html')
    open(hp, 'w').write(h)
    subprocess.run(['google-chrome', '--headless=new', '--no-sandbox', '--disable-gpu', '--allow-file-access-from-files',
                    '--no-pdf-header-footer', f'--print-to-pdf={out_pdf}', 'file://' + hp],
                   capture_output=True, timeout=600)
    if outline: add_outline(out_pdf, outline)
    # compresión sin pérdida (si qpdf está instalado)
    if subprocess.run(['which', 'qpdf'], capture_output=True).returncode == 0:
        tmp = out_pdf + '.q'
        r = subprocess.run(['qpdf', '--object-streams=generate', '--compress-streams=y', '--recompress-flate',
                            '--compression-level=9', out_pdf, tmp], capture_output=True)
        if os.path.exists(tmp) and os.path.getsize(tmp) > 0: os.replace(tmp, out_pdf)
    return out_pdf


def add_outline(pdf, items):
    """Marcadores del PDF (barra lateral). items: [(título, anchor, [(título, anchor), ...]), ...]"""
    from pypdf import PdfReader, PdfWriter
    r = PdfReader(pdf)
    idx = {p.indirect_reference.idnum: i for i, p in enumerate(r.pages)}
    nd = {k.lstrip('/'): idx[v.page.idnum] for k, v in r.named_destinations.items()}
    w = PdfWriter(clone_from=r)
    for title, anchor, kids in items:
        if anchor not in nd: continue
        parent = w.add_outline_item(title, nd[anchor])
        for kt, ka in kids:
            if ka in nd: w.add_outline_item(kt, nd[ka], parent=parent)
    w.page_mode = '/UseOutlines'
    tmp = pdf + '.tmp'
    with open(tmp, 'wb') as f: w.write(f)
    os.replace(tmp, pdf)
