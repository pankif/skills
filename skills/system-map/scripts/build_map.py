"""Проверка модели, снимки оснований и автономная интерактивная карта. Python 3.8+."""
import argparse
import copy
import hashlib
import html
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from urllib.parse import quote, urlparse

SKILL = Path(__file__).resolve().parent.parent
ID = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
TYPES = {"entry", "service", "step", "decision", "data", "event", "success", "error", "external"}
KINDS = {"code": "Код", "config": "Конфигурация", "docs": "Документация",
         "test": "Тест · просмотрен", "runtime": "Наблюдение", "user": "Сведения владельца",
         "example": "Учебный пример"}


class MapError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise MapError(message)


def text(value, label):
    require(isinstance(value, str) and bool(value.strip()), label + ": нужна непустая строка")


def identifier(value, label):
    require(isinstance(value, str) and bool(ID.fullmatch(value)), label + ": неверный id")


def git(root, *args):
    try:
        result = subprocess.run(["git", "-C", str(root), *args], capture_output=True,
                                timeout=15, encoding="utf-8", errors="replace")
        return result.stdout.strip() if result.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired):
        return None


def git_bytes(root, *args):
    try:
        result = subprocess.run(["git", "-C", str(root), *args], capture_output=True, timeout=15)
        return result.stdout if result.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired):
        return None


def github_base(remote):
    if not remote:
        return None
    match = re.fullmatch(r"(?:https://github\.com/|git@github\.com:)([\w.-]+/[\w.-]+?)(?:\.git)?/?", remote)
    return "https://github.com/" + match.group(1) if match else None


def safe_path(root, relative):
    text(relative, "source.path")
    require("\\" not in relative and not PurePosixPath(relative).is_absolute()
            and ":" not in relative and ".." not in Path(relative).parts,
            "source.path: нужен относительный путь внутри источника")
    target = (root / relative).resolve()
    require(root == target or root in target.parents, "source.path выходит за пределы источника")
    require(target.is_file(), "нет файла: " + str(target))
    return target


def capture_sources(model, roots):
    repositories = model["snapshot"].get("repositories", [])
    repo_ids = {repo["id"] for repo in repositories}
    require(set(roots).issubset(repo_ids), "--root содержит источник, которого нет в snapshot.repositories")
    states = {}
    for repo in repositories:
        repo_id = repo["id"]
        if repo_id not in roots:
            continue
        root = roots[repo_id].resolve()
        require(root.is_dir(), "нет папки: " + str(root))
        # A source folder can be a subdirectory of a Git checkout.
        git_top = git(root, "rev-parse", "--show-toplevel")
        top = Path(git_top).resolve() if git_top else root
        head = git(root, "rev-parse", "HEAD")
        status = git(root, "status", "--porcelain") if head else None
        repo.update(head=head or "", branch=git(root, "branch", "--show-current") or "",
                    dirty=bool(status) if status is not None else None)
        repo["url"] = github_base(git(root, "remote", "get-url", "origin")) or ""
        states[repo_id] = (root, top, head, repo["url"])
    for source_id, source in model["sources"].items():
        repo_id = source["repo"]
        if repo_id not in states:
            require(isinstance(source.get("code"), str) and source.get("fileHash"),
                    source_id + ": дайте --root " + repo_id + "=PATH для снятия фрагмента")
            if source.get("redact"):
                source["code"] = "[Фрагмент скрыт: " + source.get("note", "секретные значения") + "]"
            continue
        root, top, head, remote = states[repo_id]
        target = safe_path(root, source["path"])
        raw = target.read_bytes()
        try:
            lines = raw.decode("utf-8-sig").splitlines()
        except UnicodeDecodeError:
            raise MapError(source_id + ": источник должен быть UTF-8 текстом")
        start, end = source["start"], source["end"]
        require(end <= len(lines), source_id + ": конец диапазона вне файла")
        redacted = source.get("redact", False)
        require(not (target.name == ".env" or target.suffix in {".pem", ".key"}) or redacted,
                source_id + ": для файла с секретами укажите redact: true")
        source["code"] = ("[Фрагмент скрыт: " + source.get("note", "секретные значения") + "]"
                          if redacted else "\n".join(str(i + 1) + ": " + lines[i]
                                                    for i in range(start - 1, end)))
        relative = target.relative_to(top).as_posix()
        committed = git_bytes(top, "show", "HEAD:" + relative) if head else None
        # Compare normalized lines: Git may use LF while the worktree uses CRLF.
        matches = (committed is not None and
                   committed.decode("utf-8-sig", errors="replace").splitlines() == lines)
        source.update(file=repo_id + "/" + source["path"],
                      fileHash=hashlib.sha256(raw).hexdigest(), sha=head or "", local=not matches)
        source["url"] = (remote + "/blob/" + head + "/" + quote(relative, safe="/")
                         + "#L" + str(start) + "-L" + str(end)) if matches and remote else None
    if roots:
        model["snapshot"]["capturedAt"] = datetime.now(timezone.utc).isoformat(timespec="seconds")


def validate(model, captured=False):
    require(isinstance(model, dict), "корень модели должен быть объектом")
    require(model.get("schemaVersion") == 1, "schemaVersion должен быть 1")
    snapshot = model.get("snapshot", {})
    require(isinstance(snapshot, dict), "snapshot должен быть объектом")
    for key in ("key", "name", "date", "scope"):
        text(snapshot.get(key), "snapshot." + key)
    identifier(snapshot["key"], "snapshot.key")
    repositories = snapshot.get("repositories", [])
    require(isinstance(repositories, list), "snapshot.repositories должен быть массивом")
    repo_ids = set()
    for repo in repositories:
        require(isinstance(repo, dict), "источник должен быть объектом")
        identifier(repo.get("id"), "repository.id")
        require(repo["id"] not in repo_ids, "повтор repository.id: " + repo["id"])
        repo_ids.add(repo["id"])
        text(repo.get("name"), "repository.name")
    sources = model.get("sources")
    require(isinstance(sources, dict), "sources должен быть объектом")
    for source_id, source in sources.items():
        identifier(source_id, "source id")
        require(isinstance(source, dict), source_id + ": нужен объект")
        require(source.get("repo") in repo_ids, source_id + ": неизвестный repo")
        path = source.get("path")
        text(path, source_id + ".path")
        require(not PurePosixPath(path).is_absolute() and ".." not in PurePosixPath(path).parts
                and "\\" not in path and ":" not in path, source_id + ": неверный path")
        start, end = source.get("start"), source.get("end")
        require(type(start) is int and type(end) is int and 0 < start <= end,
                source_id + ": неверный диапазон строк")
        require(source.get("kind") in KINDS, source_id + ": неизвестный kind")
        if source.get("url"):
            require(urlparse(source["url"]).scheme == "https", source_id + ": url должен быть https")
        if captured:
            text(source.get("code"), source_id + ".code")
            require(bool(re.fullmatch(r"[a-f0-9]{64}", source.get("fileHash", ""))),
                    source_id + ": нет SHA-256 файла")
    views = model.get("views")
    require(isinstance(views, dict) and bool(views), "views должен содержать хотя бы одну карту")
    require(model.get("defaultView") in views, "defaultView не найден")
    warnings = []
    for view_id, view in views.items():
        identifier(view_id, "view id")
        require(isinstance(view, dict), view_id + ": нужен объект")
        for key in ("title", "description", "gaps"):
            text(view.get(key), view_id + "." + key)
        layers = view.get("layers")
        require(isinstance(layers, list) and bool(layers) and
                all(isinstance(x, str) and x.strip() for x in layers), view_id + ": нужны layers")
        require(isinstance(view.get("nodes"), list) and bool(view["nodes"]), view_id + ": нужны nodes")
        require(isinstance(view.get("edges"), list), view_id + ": нужен массив edges")
        node_ids, occupied = set(), set()
        for node in view["nodes"]:
            require(isinstance(node, dict), view_id + ": узел должен быть объектом")
            node_id = node.get("id")
            identifier(node_id, view_id + ".node.id")
            require(node_id not in node_ids, view_id + ": повтор узла " + node_id)
            node_ids.add(node_id)
            text(node.get("title"), node_id + ".title")
            require(node.get("type") in TYPES, node_id + ": неизвестный type")
            row, col = node.get("row"), node.get("col")
            require(type(row) is int and 0 <= row < len(layers) and type(col) is int and col >= 0,
                    node_id + ": row/col вне сетки")
            require((row, col) not in occupied, view_id + ": узлы занимают одну ячейку")
            occupied.add((row, col))
            if node.get("scenario"):
                require(node["scenario"] in views, node_id + ": неизвестная вложенная карта")
        edge_ids = set()
        for edge in view["edges"]:
            require(isinstance(edge, dict), view_id + ": связь должна быть объектом")
            identifier(edge.get("id"), view_id + ".edge.id")
            require(edge["id"] not in edge_ids, view_id + ": повтор связи " + edge["id"])
            edge_ids.add(edge["id"])
            text(edge.get("label"), edge["id"] + ".label")
            require(edge.get("from") in node_ids and edge.get("to") in node_ids,
                    edge["id"] + ": конец связи не найден")
            require(edge.get("lane", "auto") in {"auto", "left", "right", "top", "bottom"},
                    edge["id"] + ": неизвестный lane")
            for offset in ("labelDx", "labelDy"):
                require(type(edge.get(offset, 0)) in (int, float), edge["id"] + ": неверный " + offset)
        for item in view["nodes"] + view["edges"]:
            label = view_id + "/" + item["id"]
            text(item.get("description"), label + ".description")
            certainty = item.get("certainty", "verified")
            require(certainty in {"verified", "inferred", "unknown"}, label + ": неверный certainty")
            refs = item.get("source", [])
            refs = [refs] if isinstance(refs, str) else refs
            require(isinstance(refs, list) and all(isinstance(r, str) and r in sources for r in refs),
                    label + ": источник не найден")
            require(certainty != "verified" or bool(refs), label + ": у факта нет основания")
            if certainty != "verified":
                text(item.get("gap"), label + ": объясните границу вывода в gap")
            item["certainty"] = certainty
            item["unknown"] = certainty != "verified"
        for related in view.get("related", []):
            require(related in views, view_id + ": неизвестная связанная карта")
        if len(view["nodes"]) > 15 or len(layers) > 4 or max(n["col"] for n in view["nodes"]) > 2:
            warnings.append(view_id + ": проверьте читаемость; подробности можно вынести во вложенные карты")
        view.setdefault("short", view["title"])
        view.setdefault("group", "Карты")
        view.setdefault("icon", "network")
        view.setdefault("finding", "")
    return warnings


def render(model, fragment=False):
    template = (SKILL / "assets" / "map-template.html").read_text(encoding="utf-8")
    # Script-end and HTML delimiters from source excerpts stay JSON data.
    payload = json.dumps(model, ensure_ascii=False, separators=(",", ":"))
    payload = payload.replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e")
    payload = payload.replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    result = template.replace("__SYSTEM_MAP_DATA__", payload)
    if fragment:
        return result
    title = html.escape(model["snapshot"]["name"])
    return ('<!doctype html>\n<html lang="ru"><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>' + title + '</title><style>html,body{margin:0;background:#060d1b;}'
            'body{padding:12px;box-sizing:border-box} @media(max-width:580px){body{padding:0}}</style>'
            '<body>' + result + '</body></html>\n')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("model", type=Path, help="JSON-модель или сохранённый снимок карты")
    parser.add_argument("-o", "--output", type=Path, help="HTML; рядом будет JSON-снимок с тем же именем")
    parser.add_argument("--root", action="append", default=[], metavar="ID=PATH",
                        help="папка исходников; можно повторять для разных репозиториев")
    parser.add_argument("--check", action="store_true", help="проверить, не записывая результат")
    parser.add_argument("--fragment", action="store_true", help="HTML-фрагмент для встроенного просмотра")
    args = parser.parse_args(argv)
    try:
        roots = {}
        for binding in args.root:
            require("=" in binding, "--root: нужен ID=PATH")
            repo_id, path = binding.split("=", 1)
            require(repo_id not in roots, "повтор --root " + repo_id)
            roots[repo_id] = Path(path)
        model = json.loads(args.model.read_text(encoding="utf-8-sig"))
        model = copy.deepcopy(model)
        warnings = validate(model)
        capture_sources(model, roots)
        validate(model, captured=True)
        for warning in warnings:
            print("предупреждение: " + warning)
        print("карт: {0}, элементов: {1}, связей: {2}, оснований: {3}".format(
            len(model["views"]), sum(len(v["nodes"]) for v in model["views"].values()),
            sum(len(v["edges"]) for v in model["views"].values()), len(model["sources"])))
        if not args.check:
            require(args.output is not None, "задайте -o map.html или --check")
            require(args.output.suffix.lower() == ".html", "выходной файл должен иметь расширение .html")
            snapshot_path = args.output.with_suffix(".json")
            require(snapshot_path.resolve() != args.model.resolve(), "выходной JSON совпадает с входной моделью")
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(render(model, args.fragment), encoding="utf-8")
            snapshot_path.write_text(json.dumps(model, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            print(str(args.output) + "\n" + str(snapshot_path))
    except (MapError, OSError, json.JSONDecodeError) as error:
        print("ошибка: " + str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
