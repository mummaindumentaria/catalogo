"""Tapa 'aplanada': banner + logo + textos con sombra suave, todo en una sola imagen (sin transparencias en el PDF)."""
import os, hashlib
from PIL import Image, ImageDraw, ImageFont, ImageFilter
ROOT = os.path.dirname(os.path.abspath(__file__))
BEIGE = (0xFE, 0xF4, 0xEB)

def _font(path, size, wght=None):
    f = ImageFont.truetype(path, size)
    if wght:
        try: f.set_variation_by_axes([wght])
        except Exception: pass
    return f

def _spaced(draw, cx, y, text, font, spacing, fill):
    widths = [draw.textlength(c, font=font) for c in text]
    total = sum(widths) + spacing * (len(text) - 1)
    x = cx - total / 2
    for c, w in zip(text, widths):
        draw.text((x, y), c, font=font, fill=fill); x += w + spacing

def build(sub):
    out = f"{ROOT}/brand/cover_{hashlib.md5(sub.encode()).hexdigest()[:8]}.jpg"
    if os.path.exists(out): return out
    ban = Image.open(f'{ROOT}/brand/banner.jpg').convert('RGB')
    W, H = ban.size; tw = H // 2
    ban = ban.crop(((W - tw) // 2, 0, (W - tw) // 2 + tw, H))
    W, H = ban.size; mm = W / 108; pt = mm * 0.3528
    layer = Image.new('L', (W, H), 0)  # máscara de lo que va en beige
    logo = Image.open(f'{ROOT}/brand/logo_beige.png').getchannel('A')
    lw = int(56 * mm); logo = logo.resize((lw, int(logo.height * lw / logo.width)), Image.LANCZOS)
    y = int(11 * mm); layer.paste(logo, ((W - lw) // 2, y), logo)
    d = ImageDraw.Draw(layer)
    y += logo.height + int(2 * mm)
    f1 = _font(f'{ROOT}/fonts/Jost.ttf', int(5.8 * pt), 500)
    _spaced(d, W / 2 + 0.425 * 5.8 * pt, y, 'INDUMENTARIA', f1, 0.85 * 5.8 * pt, 255)
    y += int(5.8 * pt) + int(4 * mm)
    f2 = _font(f'{ROOT}/fonts/CormorantGaramond-Italic.ttf', int(15 * pt), 600)
    t = f'Catálogo {sub}'
    d.text((W / 2 - d.textlength(t, font=f2) / 2, y), t, font=f2, fill=255)
    # sombra: halo amplio + sombra corta
    sh1 = layer.filter(ImageFilter.GaussianBlur(2.5 * mm)).point(lambda v: int(v * .55))
    sh2 = layer.filter(ImageFilter.GaussianBlur(.6 * mm)).point(lambda v: int(v * .35))
    dark = Image.new('RGB', (W, H), (40, 20, 10))
    img = Image.composite(dark, ban, sh1); img = Image.composite(dark, img, sh2)
    img = Image.composite(Image.new('RGB', (W, H), BEIGE), img, layer)
    img.save(out, 'JPEG', quality=86, optimize=True, progressive=True)
    return out
