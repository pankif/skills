<#
Ставит скиллы из этого репозитория для Codex и/или Claude Code (Windows).

  powershell -ExecutionPolicy Bypass -File scripts\install.ps1 [-Target codex|claude|all] [-Skills имя,имя]

codex  -> $env:CODEX_SKILLS_DIR или ~\.agents\skills
claude -> $env:CLAUDE_SKILLS_DIR или ~\.claude\skills
Без -Skills — все скиллы. Установленная ранее копия скилла заменяется.
#>
param(
  [ValidateSet('codex', 'claude', 'all')] [string]$Target = 'all',
  [string[]]$Skills = @()
)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot

$codex = if ($env:CODEX_SKILLS_DIR) { $env:CODEX_SKILLS_DIR } else { Join-Path $HOME '.agents\skills' }
$claude = if ($env:CLAUDE_SKILLS_DIR) { $env:CLAUDE_SKILLS_DIR } else { Join-Path $HOME '.claude\skills' }
$dests = switch ($Target) { 'codex' { @($codex) } 'claude' { @($claude) } default { @($codex, $claude) } }

if ($Skills.Count -eq 0) {
  $Skills = Get-ChildItem (Join-Path $root 'skills') -Directory |
    Where-Object { Test-Path (Join-Path $_.FullName 'SKILL.md') } |
    ForEach-Object { $_.Name }
}

foreach ($dest in $dests) {
  New-Item -ItemType Directory -Force -Path $dest | Out-Null
  foreach ($n in $Skills) {
    $src = Join-Path $root "skills\$n"
    if (-not (Test-Path (Join-Path $src 'SKILL.md'))) { throw "нет скилла: $n" }
    $to = Join-Path $dest $n
    if (Test-Path $to) { Remove-Item -Recurse -Force $to }
    Copy-Item -Recurse $src $to
    Write-Output "$n -> $to"
  }
}
Write-Output 'Готово. Перезапустите Codex или Claude Code, чтобы скиллы подхватились.'
