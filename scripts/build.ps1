# 包装脚本：不安装包也能跑，自动设置 PYTHONPATH 与临时目录。
# 例：scripts\build.ps1 build --title "周末练习" --group-by tag --answers end
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$Rest
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

# 仓库内开发用：把 src 放前面，venv 的 site-packages 用通配找（不写死 python3.x / Lib）
$env:PYTHONPATH = "$root\src"
if (Test-Path "$root\.venv\Lib\site-packages") {
    $env:PYTHONPATH = "$env:PYTHONPATH;$root\.venv\Lib\site-packages"
} elseif (Test-Path "$root\.venv\lib") {
    # Linux / macOS 的 venv 布局
    $site = Get-ChildItem "$root\.venv\lib" -Directory -Filter "python*" |
        Select-Object -First 1
    if ($site) { $env:PYTHONPATH = "$env:PYTHONPATH;$($site.FullName)\site-packages" }
}
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
