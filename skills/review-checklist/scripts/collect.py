"""Сводит решения владельца с пунктами.

python3 collect.py ITEMS.json DECISIONS [--md DOC.md]

DECISIONS — одно из:
  * папка с <id>.json (ArtifactData list с out_dir, Claude);
  * <key>-decisions.json (serve.py или кнопка «Скачать решения»);
  * текстовый файл из кнопки «Скопировать решения» (строки «Код — Решение — комментарий»).
--md заменяет раздел «## Решения владельца» в markdown-копии.
Только стандартная библиотека Python 3.8+.
"""
import json
import os
import re
import sys

NAMES = {'yes': 'Делаем', 'no': 'Не делаем', 'discuss': 'Обсудить', '': 'Без решения'}


def read_decisions(src, items):
    dec = {}
    if os.path.isdir(src):
        for f in os.listdir(src):
            if f.endswith('.json'):
                d = json.load(open(os.path.join(src, f), encoding='utf-8'))
                dec[f[:-5]] = d
        return dec
    text = open(src, encoding='utf-8-sig').read()
    if text.lstrip().startswith('{'):
        data = json.loads(text)
        return data.get('decisions', data)
    by_code = {i['code']: i['id'] for i in items}
    back = {v.lower(): k for k, v in NAMES.items()}
    for line in text.splitlines():
        parts = [p.strip() for p in line.strip().split(' — ', 2)]
        if len(parts) >= 2 and parts[0] in by_code:
            dec[by_code[parts[0]]] = {'status': back.get(parts[1].lower(), ''),
                                      'comment': parts[2] if len(parts) > 2 else ''}
    return dec


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    items = json.load(open(sys.argv[1], encoding='utf-8'))
    dec = read_decisions(sys.argv[2], items)

    groups = {k: [] for k in ('yes', 'discuss', 'no', '')}
    for i in items:
        d = dec.get(i['id']) or {}
        st, cm = d.get('status') or '', (d.get('comment') or '').strip()
        groups[st if st in groups else ''].append((i, cm))

    L = ['Итого: ' + ', '.join(f'{NAMES[k].lower()} — {len(v)}' for k, v in groups.items()) + '.\n']
    for k in ('yes', 'discuss', 'no', ''):
        if groups[k]:
            L.append(f'### {NAMES[k]}\n')
            L += [f"- **{i['code']}** {i['title']}" + (f' — *{cm}*' if cm else '') for i, cm in groups[k]]
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
