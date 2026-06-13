# creature-forge — Windows task entry. Mirrors the Makefile; both delegate to
# tasks.py so `make verify` (Linux) and `.\make.ps1 verify` (Windows) are identical.
#   Usage:  .\make.ps1 <target> [args...]
#   Targets: setup | run | verify | schemas | test | clean
param(
    [Parameter(Position = 0)][string]$Target = "verify",
    [Parameter(ValueFromRemainingArguments = $true)][string[]]$Rest
)

$py = if (Test-Path ".\.venv\Scripts\python.exe") { ".\.venv\Scripts\python.exe" } else { "python" }
& $py tasks.py $Target @Rest
exit $LASTEXITCODE
