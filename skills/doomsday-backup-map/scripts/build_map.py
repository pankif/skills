#!/usr/bin/env python3
"""Проверка и сборка карты «бэкапов судного дня».

Примеры:
  python build_map.py data/*.json --check          # только проверить
  python build_map.py data/*.json -o map.html      # проверить и собрать страницу
  python build_map.py support.json moderation.json -o map.html --title "Бэкапы судного дня"
  python build_map.py data/*.json --apply changes.json -o map.html
                                                   # перенести в данные статусы, изменённые на карте

--apply принимает JSON из кнопки «Скопировать для агента» на карте и меняет статусы
прямо в файлах данных (файлы перезаписываются с отступом в 2 пробела).

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
NAME_MAX, TECH_MAX = 40, 48
CYR = re.compile(r"[А-Яа-яЁё]")
# Имена хранилищ остаются системными (support_db, call-recordings), остальные подписи — по-русски
SYSTEM_NAME_KINDS = {"db", "search", "analytics", "object"}
# Протоколы и аббревиатуры, которые в подписях связей можно оставить латиницей
PROTOCOLS = {"websocket", "grpc", "http", "https", "http/2", "rest", "sql", "imap", "smtp", "sip", "ari", "oidc", "jdbc",
             "amqp", "s3", "mqtt", "ldap", "ldaps", "graphql", "soap", "ftp", "sftp", "nfs", "smb", "tcp", "udp", "api",
             "ssh", "rpc", "odbc", "saml", "kerberos", "ws", "wss", "ssl", "tls", "dns", "json", "xml", "csv", "pdf"}
EDITABLE = {"no", "unknown", "skip"}
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
    note = str(it.get("note") or "")
    if len(note) > 3 and not CYR.search(note):
        rep.warn(w, f"note «{note}» не на русском — опишите причину по-русски, имена систем можно оставить")
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
        if s.get("name") and not CYR.search(str(s["name"])):
            rep.warn(sw, "название сервиса не на русском")
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
            if sec.get("name") and not CYR.search(str(sec["name"])):
                rep.warn(xw, "название раздела не на русском")
            if sec.get("desc") and not CYR.search(str(sec["desc"])):
                rep.warn(xw, "описание раздела не на русском")
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
                if c.get("kind") not in SYSTEM_NAME_KINDS and not CYR.search(str(c["name"])):
                    rep.warn(cw, "подпись не на русском: в name — что это для раздела по-русски («API обращений»), "
                                 "системное имя — первым в tech («tickets-api · Go»)")
                if c.get("desc") and not CYR.search(str(c["desc"])):
                    rep.warn(cw, "desc не на русском")
                if len(str(c["name"])) > NAME_MAX:
                    rep.warn(cw, f"имя длиннее {NAME_MAX} символов займёт на ноде три строки и больше — по возможности сократите")
                if len(str(c.get("tech") or "")) > TECH_MAX:
                    rep.warn(cw, f"tech длиннее {TECH_MAX} символов — оставьте системное имя и технологию")
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
                label = str(l[2] if isinstance(l, list) and len(l) > 2 else (l.get("label") if isinstance(l, dict) else "") or "")
                foreign = [t for t in re.findall(r"[A-Za-z][A-Za-z0-9/+._-]*", label)
                           if t.lower() not in PROTOCOLS and not t.isupper() and not CYR.search(label)]
                if foreign:
                    rep.warn(xw, f"подпись связи {a} → {b} «{label}» не на русском — переведите (чтение, запись, события); "
                                 f"протоколы вроде SQL, REST, IMAP можно оставить")
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


def apply_changes(paths, changes_path):
    """Переносит в файлы данных статусы, изменённые на карте. Возвращает число применённых изменений."""
    try:
        doc = json.loads(Path(changes_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        sys.exit(f"{changes_path}: не удалось прочитать изменения ({e})")
    changes = doc.get("changes") if isinstance(doc, dict) else doc
    if not isinstance(changes, list):
        sys.exit(f"{changes_path}: ожидается объект с ключом changes, как его копирует карта")
    files = {p: json.loads(Path(p).read_text(encoding="utf-8")) for p in paths}
    touched, applied, skipped = set(), [], []
    for ch in changes:
        where = " / ".join(str(ch.get(k)) for k in ("service", "section", "component", "item", "child") if ch.get(k))
        status = ch.get("status")
        if status not in EDITABLE:
            skipped.append(f"{where}: статус «{status}» — на карте меняются только no, unknown, skip")
            continue
        target, file_of = None, None
        for p, data in files.items():
            services = data.get("services") if "services" in data else [data]
            for s in services or []:
                if str(s.get("id")) != str(ch.get("service")):
                    continue
                for sec in s.get("sections") or []:
                    if str(sec.get("id")) != str(ch.get("section")):
                        continue
                    for c in sec.get("components") or []:
                        if str(c.get("id")) != str(ch.get("component")):
                            continue
                        for it in c.get("items") or []:
                            if it.get("name") != ch.get("item"):
                                continue
                            if ch.get("child"):
                                it = next((k for k in it.get("children") or [] if k.get("name") == ch["child"]), None)
                            if it is not None:
                                target, file_of = it, p
        if target is None:
            skipped.append(f"{where}: объект не найден в данных")
            continue
        if target.get("status") == "yes":
            skipped.append(f"{where}: в данных уже «yes» — подтверждённую копию с карты не меняем")
            continue
        old = target.get("status") or "наследуется"
        if old == status:
            continue
        target["status"] = status
        touched.add(file_of)
        note = f" (note: {target['note']})" if target.get("note") else ""
        applied.append(f"{where}: {old} → {status}{note}")
    for p in touched:
        Path(p).write_text(json.dumps(files[p], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Изменения с карты: применено {len(applied)}, пропущено {len(skipped)}")
    for a in applied:
        print("  ✓", a)
    for s_ in skipped:
        print("  –", s_)
    if applied:
        print("  Проверьте note у изменённых объектов: старая причина могла перестать подходить.")
    return len(applied)


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
    ap.add_argument("--apply", metavar="CHANGES", help="JSON изменений с карты: перенести статусы в файлы данных")
    a = ap.parse_args()

    if a.apply:
        apply_changes(a.files, a.apply)

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
