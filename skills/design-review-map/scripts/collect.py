"""Сводит решения владельца с экранами.

python3 collect.py SCREENS.json DECISIONS [--md DOC.md]

DECISIONS — одно из:
  * папка с <id>.json (ArtifactData list с out_dir, Claude);
  * <key>-decisions.json (serve.py или кнопка «Скачать решения»);
  * текстовый файл из кнопки «Скопировать решения».
--md заменяет раздел «## Решения владельца» в markdown-копии.
Только стандартная библиотека Python 3.8+.
"""
import json
import os
import re
import sys

NAMES = {'fix': 'На доработку', 'ok': 'Принято', '': 'Без решения'}
TEXT_STATUS = {'доработать': 'fix', 'принято': 'ok', 'без решения': ''}


def clean(s):
    return re.sub(r'\s+', ' ', str(s or '')).strip()


def note(phrases, text):
    parts = []
    if phrases:
        parts.append(', '.join(clean(p) for p in phrases))
    if clean(text):
        parts.append(clean(text))
    return '. '.join(parts)


def lines_of(d):
    """Строки заметок в том же виде, что у кнопки «Скопировать решения»."""
    out = []
    whole = note(list(d.get('tags') or []) + list(d.get('phrases') or []), d.get('comment'))
    if whole:
        out.append('Весь экран: ' + whole)
    for k, p in enumerate(d.get('pins') or [], 1):
        p = p or {}
        head = f"Точка {k} (x {round(float(p.get('x') or 0) * 100)}%, y {round(float(p.get('y') or 0) * 100)}%)"
        n = note(p.get('phrases') or [], p.get('text'))
        out.append(f'{head}: {n}' if n else head)
    return out


def read_decisions(src, screens):
    """id экрана -> {'status': 'ok'|'fix'|'', 'lines': [...]}"""
    dec = {}
    if os.path.isdir(src):
        for f in os.listdir(src):
            if f.endswith('.json'):
                d = json.load(open(os.path.join(src, f), encoding='utf-8'))
                if isinstance(d.get('data'), dict) and 'status' not in d:
                    d = d['data']
                dec[f[:-5]] = d
    else:
        text = open(src, encoding='utf-8-sig').read()
        if text.lstrip().startswith('{'):
            data = json.loads(text)
            dec = data.get('decisions', data)
        else:
            by_code = {s['code']: s['id'] for s in screens}
            head = re.compile(r'^(\S+) .*: (принято|доработать|без решения)$')
            for block in re.split(r'\n\s*\n', text.replace('\r\n', '\n')):
                rows = [r.strip() for r in block.strip().splitlines() if r.strip()]
                m = head.match(rows[0]) if rows else None
                if m and m.group(1) in by_code:
                    notes = [r for r in rows[1:] if r != 'Без комментария']
                    dec[by_code[m.group(1)]] = {'status': TEXT_STATUS[m.group(2)], 'lines': notes}
            return dec
    return {k: {'status': v.get('status') if v.get('status') in ('ok', 'fix') else '', 'lines': lines_of(v)}
            for k, v in dec.items() if isinstance(v, dict)}


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    screens = json.load(open(sys.argv[1], encoding='utf-8'))
    dec = read_decisions(sys.argv[2], screens)

    groups = {k: [] for k in NAMES}
    for s in screens:
        d = dec.get(s['id']) or {'status': '', 'lines': []}
        groups[d['status']].append((s, d['lines']))

    L = ['Итого: ' + ', '.join(f'{NAMES[k].lower()} {len(v)}' for k, v in groups.items()) + '.\n']
    for k in NAMES:
        if not groups[k]:
            continue
        L.append(f'### {NAMES[k]}\n')
        for s, lines in groups[k]:
            if k == 'fix' or lines:
                L.append(f"**{s['code']} {s['title']}** · `{s['image']}` · {s['w']}×{s['h']}\n")
                L += [f'- {x}' for x in lines] or ['- Без комментария']
                L.append('')
            else:
                L.append(f"- {s['code']} {s['title']}")
        if L[-1] != '':
            L.append('')
    text = '\n'.join(L)
    print(text)

    if '--md' in sys.argv:
        p = sys.argv[sys.argv.index('--md') + 1]
        md = open(p, encoding='utf-8').read()
        new = '## Решения владельца\n\n' + text + '\n'
        md, n = re.subn(r'## Решения владельца\n.*?(?=\n## |\Z)', lambda m: new, md, flags=re.S)
        if not n:
            md = md.rstrip() + '\n\n' + new
        open(p, 'w', encoding='utf-8').write(md)


if __name__ == '__main__':
    main()
