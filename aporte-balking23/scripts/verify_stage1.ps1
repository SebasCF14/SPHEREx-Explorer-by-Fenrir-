# Run from any directory; no third-party Python packages required.
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$files = @(
  'backend/spherex_explorer/main.py',
  'backend/spherex_explorer/spherex_data.py',
  'backend/spherex_explorer/spherex_analysis.py',
  'backend/spherex_explorer/astronomy_catalogs.py',
  'backend/spherex_explorer/viewer.py'
)
python -m py_compile @files
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
python scripts/verify_stage1.py
exit $LASTEXITCODE
