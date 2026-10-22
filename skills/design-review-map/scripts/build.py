"""Собирает страницу дизайн-ревью, список экранов и markdown-копию из spec.json.

python3 build.py SPEC.json OUT_DIR [--url ARTIFACT_URL] [--images embed|copy] [--template PATH]

Пишет OUT_DIR/<key>.html, OUT_DIR/<key>-screens.json, OUT_DIR/<key>.md.
--images embed (по умолчанию) — скриншоты внутри страницы, один файл.
--images copy — скриншоты рядом, в OUT_DIR/<key>-img/, плюс OUT_DIR/<key>-files.json:
  карта файлов для публикации артефакта (параметр files инструмента Artifact).
Только стандартная библиотека Python 3.8+.
"""
import base64
import html
import json
import os
import re
import shutil
import struct
import sys
from pathlib import Path

PHRASES = ['Крупнее', 'Мельче', 'Сдвинуть', 'Выровнять', 'Другой цвет', 'Убрать', 'Опечатка', 'Не по сетке']
TAGS = ['Отступы', 'Цвета', 'Шрифты', 'Тексты', 'Иконки', 'Выравнивание', 'Состояния']
MIME = {'.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.gif': 'image/gif',
        '.webp': 'image/webp', '.svg': 'image/svg+xml', '.avif': 'image/avif'}
WARN_MB, MAX_MB = 8, 15


def arg(name, default=''):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default


def plural(n, one, few, many):
    n10, n100 = n % 10, n % 100
    return one if n10 == 1 and n100 != 11 else few if 2 <= n10 <= 4 and not 12 <= n100 <= 14 else many


def svg_size(data):
    head = data[:4096].decode('utf-8', 'ignore')
    m = re.search(r'<svg\b[^>]*>', head, re.S)
    if not m:
        return None
    tag = m.group(0)
    get = lambda a: (re.search(r'\b%s\s*=\s*["\']\s*([0-9.]+)\s*(px)?\s*["\']' % a, tag) or [None, None])[1]
    w, h = get('width'), get('height')
    if w and h:
        return round(float(w)), round(float(h))
    vb = re.search(r'viewBox\s*=\s*["\']\s*[-0-9.]+[\s,]+[-0-9.]+[\s,]+([0-9.]+)[\s,]+([0-9.]+)', tag)
    return (round(float(vb.group(1))), round(float(vb.group(2)))) if vb else None


def image_size(data, ext):
    """Ширина и высота по заголовку файла: PNG, JPEG, GIF, WebP, SVG. None — не удалось."""
    if data[:8] == b'\x89PNG\r\n\x1a\n':
        return struct.unpack('>II', data[16:24])
    if data[:6] in (b'GIF87a', b'GIF89a'):
        return struct.unpack('<HH', data[6:10])
    if data[:4] == b'RIFF' and data[8:12] == b'WEBP':
        kind = data[12:16]
        if kind == b'VP8 ':
            w, h = struct.unpack('<HH', data[26:30])
            return w & 0x3fff, h & 0x3fff
        if kind == b'VP8L':
            b = data[21:25]
            return 1 + (((b[1] & 0x3f) << 8) | b[0]), 1 + (((b[3] & 0xf) << 10) | (b[2] << 2) | ((b[1] & 0xc0) >> 6))
        if kind == b'VP8X':
            return 1 + int.from_bytes(data[24:27], 'little'), 1 + int.from_bytes(data[27:30], 'little')
    if data[:2] == b'\xff\xd8':
        i = 2
        while i + 9 < len(data):
            if data[i] != 0xff:
                i += 1
                continue
            marker = data[i + 1]
            if marker in (0xd8, 0x01) or 0xd0 <= marker <= 0xd7 or marker == 0xff:
                i += 1 if marker == 0xff else 2
                continue
            seg = struct.unpack('>H', data[i + 2:i + 4])[0]
            if 0xc0 <= marker <= 0xcf and marker not in (0xc4, 0xc8, 0xcc):
                h, w = struct.unpack('>HH', data[i + 5:i + 9])
                return w, h
            i += 2 + seg
    if ext == '.svg' or data.lstrip()[:5] in (b'<?xml', b'<svg ', b'<svg\n', b'<!--'):
        return svg_size(data)
    return None


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    spec_path, out = Path(sys.argv[1]), sys.argv[2]
    url, mode = arg('--url'), arg('--images', 'embed')
    assert mode in ('embed', 'copy'), '--images: embed или copy'
    tpl_path = arg('--template', str(Path(__file__).resolve().parent.parent / 'assets' / 'template.html'))
    S = json.load(open(spec_path, encoding='utf-8'))
    os.makedirs(out, exist_ok=True)

    key = S['key']
    assert re.fullmatch(r'[A-Za-z0-9_-]+', key), 'key — латиница, цифры, _ и -'
    assert S.get('screens'), 'нужен хотя бы один экран в screens'
    prefix = S.get('prefix', 'Э')
    phrases = S.get('phrases', PHRASES)
    tags = S.get('tags', TAGS)
    base_dir = spec_path.resolve().parent
    img_dir = os.path.join(out, key + '-img')
    if mode == 'copy':
        os.makedirs(img_dir, exist_ok=True)

    screens, data_screens, files_map, total = [], [], {}, 0
    for n, sc in enumerate(S['screens'], 1):
        assert sc.get('image') and sc.get('title'), f'экран {n}: нужны image и title'
        path = Path(sc['image']) if os.path.isabs(sc['image']) else base_dir / sc['image']
        assert path.is_file(), f'экран {n}: нет файла {path}'
        raw = path.read_bytes()
        ext = path.suffix.lower()
        assert ext in MIME, f'экран {n}: формат {ext} не поддерживается, нужен один из {", ".join(MIME)}'
        size = (sc['w'], sc['h']) if sc.get('w') and sc.get('h') else image_size(raw, ext)
        assert size and size[0] > 0 and size[1] > 0, f'экран {n}: не понял размер {path.name}, укажите w и h в spec'
        sid, code = f's{n}', f'{prefix}{n}'
        if mode == 'embed':
            src = f'data:{MIME[ext]};base64,' + base64.b64encode(raw).decode('ascii')
            total += len(src)
        else:
            name = f'{n:02d}{ext}'
            shutil.copyfile(path, os.path.join(img_dir, name))
            src = f'{key}-img/{name}'
            files_map[src] = os.path.abspath(os.path.join(img_dir, name))
            total += len(raw)
        note = sc.get('note', '')
        screens.append(dict(id=sid, code=code, title=sc['title'], note=note, image=sc['image'], w=size[0], h=size[1]))
        data_screens.append(dict(id=sid, code=code, title=sc['title'], note=note, src=src, w=size[0], h=size[1]))

    mb = total / 1024 / 1024
    if mode == 'embed' and mb > MAX_MB:
        sys.exit(f'скриншоты внутри страницы весят {mb:.1f} МБ, артефакт больше 16 МБ не примет. '
                 'Сожмите их в WebP или JPEG либо соберите с --images copy')
    if mb > WARN_MB:
        print(f'предупреждение: скриншоты весят {mb:.1f} МБ, на телефоне страница будет открываться долго. '
              'Лучше WebP или JPEG шириной до 1200 px', file=sys.stderr)

    data = dict(key=key, title=S['title'], phrases=phrases, tags=tags, screens=data_screens)
    t = open(tpl_path, encoding='utf-8').read()
    for k, v in {'__TITLE__': html.escape(S['title']),
                 '__HEADING__': html.escape(S.get('heading', 'Дизайн-ревью')),
                 '__DATA__': json.dumps(data, ensure_ascii=False).replace('<', '\\u003c')}.items():
        assert k in t, k
        t = t.replace(k, v)
    base = os.path.join(out, key)
    open(base + '.html', 'w', encoding='utf-8').write(t)
    json.dump(screens, open(base + '-screens.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    if files_map:
        json.dump(files_map, open(base + '-files.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

    # markdown-копия для проекта и репозитория
    count = f"{len(screens)} {plural(len(screens), 'экран', 'экрана', 'экранов')}"
    L = [f"# {S['title']}\n"]
    if url:
        L.append(f'Решения на странице: {url}\n')
    if S.get('intro'):
        L.append(S['intro'].rstrip() + '\n')
    L.append(f'## {count.capitalize()}\n')
    L.append('| Код | Экран | Что показать | Файл |\n|---|---|---|---|')
    cell = lambda s: str(s).replace('|', '\\|').replace('\n', ' ')
    for s in screens:
        L.append(f"| {s['code']} | {cell(s['title'])} | {cell(s['note'])} | `{cell(s['image'])}` |")
    L.append('\n## Решения владельца\n\nПока нет. В работу идут только экраны с решением «Доработать».\n')
    open(base + '.md', 'w', encoding='utf-8').write('\n'.join(L))
    outs = [base + '.html', base + '-screens.json', base + '.md'] + ([base + '-files.json'] if files_map else [])
    print(*outs, f'{count}, {mb:.1f} МБ', sep='\n')


if __name__ == '__main__':
    main()
