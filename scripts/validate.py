"""Проверяет все скиллы в skills/.

python3 scripts/validate.py

Ошибки (выход 1):
  * нет SKILL.md или frontmatter;
  * name не совпадает с папкой или не kebab-case до 64 знаков;
  * description пустой, длиннее 1024 знаков или с < >;
  * упомянутые в SKILL.md файлы scripts/, assets/, references/ не существуют;
  * Python-скрипты скилла не компилируются.
Предупреждения: SKILL.md длиннее 500 строк, скилла нет в таблице README.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NAME = re.compile(r'^[a-z0-9]+(-[a-z0-9]+)*$')
REF = re.compile(r'`((?:scripts|assets|references|agents)/[^`\s]+)`')


def frontmatter(text):
    m = re.match(r'^---\n(.*?)\n---\n', text, re.S)
    if not m:
        return None
    fm = {}
    for line in m.group(1).splitlines():
        if ':' in line and not line.startswith((' ', '\t')):
            k, v = line.split(':', 1)
            fm[k.strip()] = v.strip().strip('"\'')
    return fm


def check(skill):
    errors, warnings = [], []
    md = skill / 'SKILL.md'
    if not md.exists():
        return [f'{skill.name}: нет SKILL.md'], []
    text = md.read_text(encoding='utf-8')
    fm = frontmatter(text)
    if fm is None:
        return [f'{skill.name}: нет frontmatter между ---'], []
    name, desc = fm.get('name', ''), fm.get('description', '')
    if name != skill.name:
        errors.append(f'{skill.name}: name «{name}» не совпадает с папкой')
    if not NAME.match(name) or len(name) > 64:
        errors.append(f'{skill.name}: name — строчная латиница, цифры и дефисы, до 64 знаков')
    if not desc:
        errors.append(f'{skill.name}: пустой description')
    if len(desc) > 1024:
        errors.append(f'{skill.name}: description длиннее 1024 знаков ({len(desc)})')
    if '<' in desc or '>' in desc:
        errors.append(f'{skill.name}: в description нельзя < и >')
    for ref in sorted(set(REF.findall(text))):
        path = ref.split('#')[0].rstrip('.,;:')
        if '<' in path or '*' in path:
            continue
        if not (skill / path).exists():
            errors.append(f'{skill.name}: в SKILL.md упомянут {path}, файла нет')
    for py in skill.rglob('*.py'):
        try:
            compile(py.read_text(encoding='utf-8'), str(py), 'exec')
        except SyntaxError as e:
            errors.append(f'{skill.name}: {py.relative_to(skill)}:{e.lineno} не компилируется: {e.msg}')
    lines = text.count('\n')
    if lines > 500:
        warnings.append(f'{skill.name}: SKILL.md {lines} строк — лучше вынести подробности в references/')
    return errors, warnings


def main():
    skills = sorted(p for p in (ROOT / 'skills').iterdir() if p.is_dir())
    readme = (ROOT / 'README.md').read_text(encoding='utf-8') if (ROOT / 'README.md').exists() else ''
    errors, warnings = [], []
    for s in skills:
        e, w = check(s)
        errors += e
        warnings += w
        if f'skills/{s.name}' not in readme:
            warnings.append(f'{s.name}: нет в таблице README')
    for w in warnings:
        print('предупреждение:', w)
    for e in errors:
        print('ошибка:', e)
    print(f'скиллов: {len(skills)}, ошибок: {len(errors)}, предупреждений: {len(warnings)}')
    sys.exit(1 if errors else 0)


if __name__ == '__main__':
    main()
