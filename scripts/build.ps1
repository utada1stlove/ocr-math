# 包装脚本：不安装包也能跑，自动设置 PYTHONPATH 与临时目录。
# 例：scripts\build.ps1 build --title "周末练习" --group-by tag --answers end
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$Rest
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

$env:PYTHONPATH = "$root\src;$root\.venv\Lib\site-packages"
$env:TMP = "$root\.tmp"
$env:TEMP = "$root\.tmp"
$env:PYTHONIOENCODING = "utf-8"
if (-not (Test-Path $env:TMP)) { New-Item -ItemType Directory -Path $env:TMP | Out-Null }

Push-Location $root
try {
    & python -m ocrmath.cli @Rest
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
