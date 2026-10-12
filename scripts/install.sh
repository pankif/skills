#!/usr/bin/env bash
# Ставит скиллы из этого репозитория для Codex и/или Claude Code.
#
#   scripts/install.sh [codex|claude|all] [--link] [имя ...]
#
# codex  -> ${CODEX_SKILLS_DIR:-$HOME/.agents/skills}
# claude -> ${CLAUDE_SKILLS_DIR:-$HOME/.claude/skills}
# --link — символьные ссылки вместо копий: git pull сразу обновляет скиллы.
# Без имён — все скиллы. Установленная ранее копия скилла заменяется.
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
target="${1:-all}"
[ $# -gt 0 ] && shift
link=0
names=()
for a in "$@"; do
  if [ "$a" = "--link" ]; then link=1; else names+=("$a"); fi
done

case "$target" in
  codex) dests=("${CODEX_SKILLS_DIR:-$HOME/.agents/skills}") ;;
  claude) dests=("${CLAUDE_SKILLS_DIR:-$HOME/.claude/skills}") ;;
  all) dests=("${CODEX_SKILLS_DIR:-$HOME/.agents/skills}" "${CLAUDE_SKILLS_DIR:-$HOME/.claude/skills}") ;;
  *) echo "куда ставить: codex, claude или all" >&2; exit 2 ;;
esac

if [ ${#names[@]} -eq 0 ]; then
  for d in "$root"/skills/*/; do [ -f "$d/SKILL.md" ] && names+=("$(basename "$d")"); done
fi

for dest in "${dests[@]}"; do
  mkdir -p "$dest"
  for n in "${names[@]}"; do
    src="$root/skills/$n"
    [ -f "$src/SKILL.md" ] || { echo "нет скилла: $n" >&2; exit 1; }
    rm -rf "${dest:?}/$n"
    if [ "$link" = 1 ]; then ln -s "$src" "$dest/$n"; else cp -R "$src" "$dest/$n"; fi
    echo "$n -> $dest/$n"
  done
done
echo "Готово. Перезапустите Codex или Claude Code, чтобы скиллы подхватились."
