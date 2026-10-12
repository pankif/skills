"""Собирает страницу чек-листа, items.json и markdown-копию из spec.json.

python3 build.py SPEC.json OUT_DIR [--url ARTIFACT_URL] [--template PATH]

Пишет OUT_DIR/<key>.html, OUT_DIR/<key>-items.json, OUT_DIR/<key>.md.
Только стандартная библиотека Python 3.8+.
"""
import html
import json
import os
import re
import sys
from pathlib import Path

SEV = {3: 'высокая', 2: 'средняя', 1: 'низкая'}
FIELDS = ('area', 'sev', 'cat', 'effort', 'conf', 'title', 'problem', 'fix', 'where')


def arg(name, default=''):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default


def plural(n, one, few, many):
    n10, n100 = n % 10, n % 100
    return one if n10 == 1 and n100 != 11 else few if 2 <= n10 <= 4 and not 12 <= n100 <= 14 else many


def js(v):
    return json.dumps(v, ensure_ascii=False).replace('</', '<\\/')


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    spec_path, out = sys.argv[1], sys.argv[2]
    url = arg('--url')
    tpl_path = arg('--template', str(Path(__file__).resolve().parent.parent / 'assets' / 'template.html'))
    S = json.load(open(spec_path, encoding='utf-8'))
    os.makedirs(out, exist_ok=True)

    assert re.fullmatch(r'[A-Za-z0-9_-]+', S['key']), 'key — латиница, цифры, _ и -'
    areas = S['areas']
    by_id = {a['id']: a for a in areas}
    for a in areas:
        assert re.fullmatch(r'[A-Za-z0-9_-]+', a['id']), 'id области — латиница: ' + a['id']

    items, per_area, n_global = [], {}, 0
    for it in S['items']:
        missing = [k for k in FIELDS if k not in it]
        assert not missing, f"в пункте «{it.get('title', '?')}» нет полей: {missing}"
        a = by_id[it['area']]
        assert it['sev'] in SEV, it['title']
        assert it['effort'] in ('S', 'M', 'L'), it['title']
        assert it['conf'] in ('проверено', 'вероятно'), it['title']
        if a.get('prefix'):
            per_area[a['id']] = per_area.get(a['id'], 0) + 1
            n = per_area[a['id']]
            code, iid = a['prefix'] + str(n), f"{a['id']}{n}"
        else:
            n_global += 1
            code, iid = S['prefix'] + str(n_global), f"i{n_global}"
        items.append(dict(id=iid, code=code, **{k: it[k] for k in FIELDS}))

    count = f"{len(items)} {plural(len(items), 'пункт', 'пункта', 'пунктов')}"
    verdict = ''
    if S.get('verdict'):
        cols = ''.join(f'<div class="vcol"><span class="lbl">{html.escape(c["label"])}</span>{c["html"]}</div>'
                       for c in S['verdict'])
        verdict = (f'  <section class="verdict" aria-label="Итог">{cols}</section>\n'
                   f'  <h2 class="findings">{html.escape(S.get("findingsTitle", "Пункты"))} · {count}</h2>')

    t = open(tpl_path, encoding='utf-8').read()
    cfg = dict(areas=[[a['id'], a['name']] for a in areas], key=S['key'],
               placeholder=S.get('placeholder', 'Например: только сервер, клиент — потом'))
    for k, v in {'__TITLE__': html.escape(S['title']),
                 '__EYEBROW__': ''.join(f'<span>{e}</span>' for e in S.get('eyebrow', [])),
                 '__INTRO__': S.get('intro', ''),
                 '__VERDICT__': verdict,
                 '__FOOT__': S.get('foot', ''),
                 '__ITEMS__': js(items),
                 '__CONFIG__': js(cfg)}.items():
        assert k in t, k
        t = t.replace(k, v)
    base = os.path.join(out, S['key'])
    open(base + '.html', 'w', encoding='utf-8').write(t)
    json.dump(items, open(base + '-items.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

    # markdown-копия для проекта и репозитория
    strip = lambda s: re.sub(r'<[^>]+>', '', s)
    L = [f"# {S['title']}\n"]
    if S.get('eyebrow'):
        L.append(' · '.join(strip(e) for e in S['eyebrow']) + '\n')
    if url:
        L.append(f'Решения — на странице: {url}\n')
    if S.get('md_intro'):
        L.append(S['md_intro'].rstrip() + '\n')
    sev_counts = ', '.join(f'{SEV[s]} — {sum(1 for i in items if i["sev"] == s)}'
                           for s in (3, 2, 1) if any(i['sev'] == s for i in items))
    L.append(f"## {S.get('findingsTitle', 'Пункты')} — {count}\n\nВажность: {sev_counts}.\n")
    L.append('| Код | Важность | Область | Пункт | Объём |\n|---|---|---|---|---|')
    for i in items:
        L.append(f"| {i['code']} | {SEV[i['sev']]} | {by_id[i['area']]['name']} | {i['title']} | {i['effort']} |")
    for a in areas:
        its = [i for i in items if i['area'] == a['id']]
        if not its:
            continue
        L.append(f"\n### {a['name']}\n")
        for i in its:
            meta = f"{SEV[i['sev']].capitalize()} · {i['cat']} · объём {i['effort']}" + (
                ' · вероятно' if i['conf'] == 'вероятно' else '')
            L += [f"#### {i['code']}. {i['title']}\n", f'- **{meta}.**', f"- **Что не так:** {i['problem']}",
                  f"- **Предлагаю:** {i['fix']}", f"- **Где:** `{i['where']}`\n"]
    L.append('## Решения владельца\n\nПока нет. Следующий шаг — только из пунктов с «Делаем».\n')
    open(base + '.md', 'w', encoding='utf-8').write('\n'.join(L))
    print(base + '.html', base + '-items.json', base + '.md', count, sep='\n')


if __name__ == '__main__':
    main()
