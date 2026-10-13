#!/usr/bin/env python3
"""Проверка и сборка карты «бэкапов судного дня».

Примеры:
  python build_map.py data/*.json --check          # только проверить
  python build_map.py data/*.json -o map.html      # проверить и собрать страницу
  python build_map.py support.json moderation.json -o map.html --title "Бэкапы судного дня"

Файлы объединяются: файл с ключом "services" добавляет все свои сервисы,
файл с ключом "sections" считается одним сервисом. Сервисы с одинаковым id
сливаются (разделы добавляются, при совпадении id раздела побеждает более поздний файл).
Только стандартная библиотека Python 3.8+.
"""
import argparse
import html
import json
import re
import sys
from pathlib import Path

LAYERS = ["entry", "app", "bus", "workers", "data", "external"]
LAYER_RANK = {l: i for i, l in enumerate(LAYERS)}
KINDS = {"client", "channel", "gateway", "service", "auth", "pbx", "queue", "stream", "cache", "worker",
         "db", "search", "analytics", "object", "mail", "external"}
DATA_KINDS = {"db", "search", "analytics", "object", "mail"}
TYPES = {"schema", "table", "collection", "bucket", "topic", "queue", "cache", "cron", "config", "secret",
         "index", "mailbox", "file", "volume", "repo", "other"}
STATUSES = {"yes", "no", "skip", "unknown"}
ICONS = {"chat", "book", "phone", "star", "photo", "flag", "envelope", "bell", "shield", "section", "db",
         "service", "client", "secret", "cron", "external"}
CRON_RE = re.compile(r"^\s*(@\w+|[\d*/,\-?LW#]+(\s+[\d*/,\-?LW#A-Za-z]+){4,5})\s*$")
WHEN_RE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b|\b\d{1,2}[:.]\d{2}\b|\b\d{1,2}\s+(янв|фев|мар|апр|ма[йя]|июн|июл|авг|сен|окт|ноя|дек)",
                     re.IGNORECASE)
NAME_MAX, TECH_MAX = 28, 32
TEMPLATE = Path(__file__).resolve().parent.parent / "assets" / "map-template.html"


class Report:
    def __init__(self):
        self.errors, self.warnings = [], []

    def err(self, where, msg):
        self.errors.append(f"{where}: {msg}")

    def warn(self, where, msg):
        self.warnings.append(f"{where}: {msg}")


def load(paths, title):
    merged = {"title": title, "subtitle": None, "services": []}
    by_id = {}
    for p in paths:
        try:
            data = json.loads(Path(p).read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            sys.exit(f"{p}: не JSON ({e})")
        if isinstance(data, dict) and "services" in data:
            merged["title"] = merged["title"] or data.get("title")
            merged["subtitle"] = merged["subtitle"] or data.get("subtitle")
            services = data["services"]
        elif isinstance(data, dict) and "sections" in data:
            services = [data]
        else:
            sys.exit(f"{p}: ожидается объект с ключом services (весь каталог) или sections (один сервис)")
        for s in services:
            sid = str(s.get("id", ""))
            if sid in by_id:
                target = by_id[sid]
                known = {str(x.get("id")): i for i, x in enumerate(target["sections"])}
                for sec in s.get("sections", []):
                    if str(sec.get("id")) in known:
                        target["sections"][known[str(sec.get("id"))]] = sec
                    else:
                        target["sections"].append(sec)
            else:
                s = dict(s, sections=list(s.get("sections", [])))
                by_id[sid] = s
                merged["services"].append(s)
    merged["title"] = merged["title"] or "Бэкапы судного дня"
    merged["subtitle"] = merged["subtitle"] or "Сбор критичных данных"
    return merged


def leaves(items):
    out = []
    for it in items or []:
        kids = it.get("children") or []
        if kids:
            for c in kids:
                out.append((c, it, c.get("status") or it.get("status") or "unknown"))
        else:
            out.append((it, None, it.get("status") or "unknown"))
    return out


def check_item(it, where, rep, parent=None):
    if not isinstance(it, dict) or not it.get("name"):
        rep.err(where, "объект без name")
        return
    name = it["name"]
    w = f"{where} › {name}"
    if it.get("type") not in TYPES:
        rep.warn(w, f"type «{it.get('type')}» неизвестен, будет показан как «Объект»")
    status = it.get("status")
    if status is not None and status not in STATUSES:
        rep.err(w, f"status «{status}» — допустимо: yes, no, skip, unknown")
    if status is None and parent is None and not it.get("children"):
        rep.warn(w, "нет status — будет «не выяснено»")
    eff = status or (parent or {}).get("status")
    if eff == "yes" and not it.get("where") and parent is None:
        rep.warn(w, "status yes без where — где лежит копия?")
    if eff in ("no", "unknown", "skip") and not it.get("note") and (parent is None or status):
        rep.warn(w, f"status {eff} без note — почему?")
    for field in ("size", "name"):
        v = str(it.get(field) or "")
        if CRON_RE.match(v):
            rep.warn(w, f"в {field} похоже расписание крона «{v}» — для разовой акции расписание не указываем")
    for field in ("where", "note"):
        v = str(it.get(field) or "")
        if WHEN_RE.search(v):
            rep.warn(w, f"в {field} есть дата или время «{v}» — для разовой акции не нужно, проверьте")
    if it.get("children"):
        if parent is not None:
            rep.err(w, "вложенность глубже одного уровня не поддерживается")
        if len(it["children"]) > 15:
            rep.warn(w, f"{len(it['children'])} дочерних — оставьте критичные (до ~15), остальное одной строкой «… ещё N»")
        for c in it["children"]:
            check_item(c, w, rep, parent=it)


def check(data, rep):
    if not data["services"]:
        rep.err("каталог", "нет ни одного сервиса")
    seen_services = set()
    for s in data["services"]:
        sw = f"сервис «{s.get('name') or s.get('id')}»"
        if not s.get("id") or not s.get("name"):
            rep.err(sw, "нужны id и name")
        if s.get("id") in seen_services:
            rep.err(sw, "повтор id сервиса")
        seen_services.add(s.get("id"))
        if s.get("icon") and s["icon"] not in ICONS:
            rep.warn(sw, f"icon «{s['icon']}» неизвестна")
        if not s.get("sections"):
            rep.err(sw, "нет разделов")
        sec_ids = set()
        for sec in s.get("sections", []):
            xw = f"{sw} / раздел «{sec.get('name') or sec.get('id')}»"
            if not sec.get("id") or not sec.get("name"):
                rep.err(xw, "нужны id и name")
            if sec.get("id") in sec_ids:
                rep.err(xw, "повтор id раздела")
            sec_ids.add(sec.get("id"))
            comps = sec.get("components") or []
            if not comps:
                rep.err(xw, "нет компонентов")
            ids, names = {}, {}
            for c in comps:
                cw = f"{xw} / {c.get('name') or c.get('id')}"
                cid = c.get("id")
                if not cid or not c.get("name"):
                    rep.err(cw, "нужны id и name")
                    continue
                if cid in ids:
                    rep.err(cw, f"повтор id «{cid}»")
                ids[cid] = c
                key = str(c["name"]).strip().lower()
                if key in names:
                    rep.warn(cw, f"имя совпадает с «{names[key]}» — возможный дубль из разных источников")
                names[key] = cid
                if c.get("layer") not in LAYERS:
                    rep.err(cw, f"layer «{c.get('layer')}» — допустимо: {', '.join(LAYERS)}")
                if c.get("kind") not in KINDS:
                    rep.warn(cw, f"kind «{c.get('kind')}» неизвестен, будет показан как сервис")
                if len(str(c["name"])) > NAME_MAX:
                    rep.warn(cw, f"имя длиннее {NAME_MAX} символов обрежется на карте — сократите, полное имя перенесите в desc")
                if len(str(c.get("tech") or "")) > TECH_MAX:
                    rep.warn(cw, f"tech длиннее {TECH_MAX} символов обрежется")
                if c.get("kind") in DATA_KINDS and not c.get("items"):
                    rep.warn(cw, "хранилище без items — что в нём лежит и есть ли это в бэкапе?")
                if not c.get("sources"):
                    rep.warn(cw, "нет sources — откуда сведения?")
                for it in c.get("items") or []:
                    check_item(it, cw, rep)
            linked = set()
            for l in sec.get("links") or []:
                if isinstance(l, list):
                    a, b = (l + [None, None])[:2]
                elif isinstance(l, dict):
                    a, b = l.get("from"), l.get("to")
                else:
                    rep.err(xw, f"связь {l!r}: ожидается [from, to, label] или {{from, to, label}}")
                    continue
                if a not in ids or b not in ids:
                    rep.err(xw, f"связь {a} → {b}: нет компонента с таким id")
                    continue
                if a == b:
                    rep.err(xw, f"связь {a} → {b} сама на себя")
                    continue
                linked.update([a, b])
                la, lb = LAYER_RANK.get(ids[a].get("layer"), 0), LAYER_RANK.get(ids[b].get("layer"), 0)
                if la > lb:
                    rep.warn(xw, f"связь {a} → {b} идёт снизу вверх — проверьте направление (откуда → к чему обращается)")
            for cid, c in ids.items():
                if cid not in linked and c.get("layer") != "entry":
                    rep.warn(f"{xw} / {c.get('name')}", "ни одной связи — к кому обращается и кто обращается к нему?")
            if not any(c.get("layer") == "entry" for c in comps):
                rep.warn(xw, "нет точек входа (layer entry) — корень раздела привяжется к верхним компонентам")


def summary(data):
    lines, unknown = [], []
    totals = {"yes": 0, "no": 0, "unknown": 0, "skip": 0}
    for s in data["services"]:
        for sec in s.get("sections", []):
            t = {"yes": 0, "no": 0, "unknown": 0, "skip": 0}
            for c in sec.get("components") or []:
                for leaf, parent, st in leaves(c.get("items")):
                    st = st if st in t else "unknown"
                    t[st] += 1
                    if st == "unknown":
                        name = f"{parent['name']}.{leaf.get('name')}" if parent else leaf.get("name")
                        unknown.append(f"{s.get('name')} / {sec.get('name')} / {c.get('name')}: {name}"
                                       + (f" — {leaf.get('note') or (parent or {}).get('note')}" if (leaf.get('note') or (parent or {}).get('note')) else ""))
            for k in totals:
                totals[k] += t[k]
            lines.append(f"  {s.get('name')} / {sec.get('name')}: в бэкапе {t['yes']}, нет {t['no']}, "
                         f"не выяснено {t['unknown']}, не нужно {t['skip']}")
    head = (f"Итого: в бэкапе {totals['yes']}, нет {totals['no']}, не выяснено {totals['unknown']}, "
            f"не нужно {totals['skip']}")
    return head, lines, unknown


def build(data, out):
    if not TEMPLATE.exists():
        sys.exit(f"Нет шаблона {TEMPLATE}")
    tpl = TEMPLATE.read_text(encoding="utf-8")
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    page = tpl.replace("__MAP_TITLE__", html.escape(data["title"]), 1).replace("__MAP_DATA__", payload, 1)
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_text(page, encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(description="Проверка и сборка карты бэкапов")
    ap.add_argument("files", nargs="+", help="JSON-файлы каталога или отдельных сервисов")
    ap.add_argument("-o", "--out", help="куда записать HTML (по умолчанию map.html)")
    ap.add_argument("--check", action="store_true", help="только проверить, не собирать")
    ap.add_argument("--title", help="заголовок каталога")
    ap.add_argument("--force", action="store_true", help="собрать, даже если есть ошибки")
    ap.add_argument("--quiet", action="store_true", help="не печатать предупреждения, только ошибки и итог")
    a = ap.parse_args()

    data = load(a.files, a.title)
    rep = Report()
    check(data, rep)
    head, lines, unknown = summary(data)

    if rep.errors:
        print(f"Ошибки ({len(rep.errors)}):")
        for e in rep.errors:
            print("  ✗", e)
    if rep.warnings and not a.quiet:
        print(f"Предупреждения ({len(rep.warnings)}):")
        for w in rep.warnings:
            print("  !", w)
    print(head)
    for l in lines:
        print(l)
    if unknown:
        print(f"Не выяснено ({len(unknown)}) — вопросы владельцам:")
        for u in unknown:
            print("  ?", u)

    if a.check:
        sys.exit(1 if rep.errors else 0)
    if rep.errors and not a.force:
        sys.exit("Страница не собрана: исправьте ошибки или добавьте --force")
    out = a.out or "map.html"
    build(data, out)
    print(f"Готово: {out}")


if __name__ == "__main__":
    main()
