"""Собирает zip скиллов для загрузки в приложение Claude.

python3 scripts/package.py [имя ...]

Без имён — все скиллы. Результат: dist/<имя>.zip, внутри папка <имя>/ с SKILL.md.
"""
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKIP = {'__pycache__', '.DS_Store'}


def pack(skill, dist):
    out = dist / f'{skill.name}.zip'
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
        for f in sorted(skill.rglob('*')):
            if f.is_file() and not SKIP.intersection(f.parts) and f.suffix != '.pyc':
                z.write(f, Path(skill.name) / f.relative_to(skill))
    return out


def main():
    names = sys.argv[1:]
    skills = sorted(p for p in (ROOT / 'skills').iterdir() if p.is_dir() and (p / 'SKILL.md').exists())
    if names:
        missing = set(names) - {s.name for s in skills}
        if missing:
            sys.exit('нет таких скиллов: ' + ', '.join(sorted(missing)))
        skills = [s for s in skills if s.name in names]
    dist = ROOT / 'dist'
    dist.mkdir(exist_ok=True)
    for s in skills:
        print(pack(s, dist).relative_to(ROOT))


if __name__ == '__main__':
    main()
