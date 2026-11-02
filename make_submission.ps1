# Build the competition submission ZIP safely.
#
# It puts the right files into a clean folder and zips them:
#   output\  -> level1.csv, level2.csv
#   source\  -> all code, README.md, .env.example, requirements.txt
#   demo\    -> demo.mp4 (only if the folder exists)
#
# It REMOVES secrets and junk so they are never uploaded:
#   .env (your real API key), cache\, __pycache__\, *.pyc
#
# Run it from the project folder:
#   powershell -ExecutionPolicy Bypass -File .\make_submission.ps1

$ErrorActionPreference = 'Stop'
$root  = Split-Path -Parent $MyInvocation.MyCommand.Path
$stage = Join-Path $root '_submission_stage'
$zip   = Join-Path $root 'submission.zip'

# 1. Safety check: the two result files must exist first.
$l1 = Join-Path $root 'output\level1.csv'
$l2 = Join-Path $root 'output\level2.csv'
if (-not (Test-Path $l1) -or -not (Test-Path $l2)) {
    Write-Host "ERROR: output\level1.csv or output\level2.csv is missing." -ForegroundColor Red
    Write-Host "Run the solution first, then run this script again." -ForegroundColor Red
    exit 1
}

# 2. Start from a clean staging folder.
if (Test-Path $stage) { Remove-Item $stage -Recurse -Force }
if (Test-Path $zip)   { Remove-Item $zip -Force }
New-Item -ItemType Directory -Path $stage | Out-Null

# 3. Copy the result CSVs.
New-Item -ItemType Directory -Path (Join-Path $stage 'output') | Out-Null
Copy-Item $l1 (Join-Path $stage 'output')
Copy-Item $l2 (Join-Path $stage 'output')

# 4. Copy the source code, then delete secrets and junk from the copy.
Copy-Item (Join-Path $root 'source') (Join-Path $stage 'source') -Recurse
$stagedSource = Join-Path $stage 'source'
Get-ChildItem $stagedSource -Recurse -Force -File |
    Where-Object { $_.Name -eq '.env' -or $_.Extension -eq '.pyc' } |
    Remove-Item -Force
Get-ChildItem $stagedSource -Recurse -Force -Directory |
    Where-Object { $_.Name -eq '__pycache__' } |
    Remove-Item -Recurse -Force

# 5. Copy the demo video folder only if you made one.
$demo = Join-Path $root 'demo'
if (Test-Path $demo) { Copy-Item $demo (Join-Path $stage 'demo') -Recurse }

# 6. Make the ZIP, then remove the staging folder.
Compress-Archive -Path (Join-Path $stage '*') -DestinationPath $zip
Remove-Item $stage -Recurse -Force

# 7. Report what was built and check the 15 MB limit.
$sizeMB = [math]::Round((Get-Item $zip).Length / 1MB, 2)
Write-Host ""
Write-Host "Created: $zip  ($sizeMB MB)" -ForegroundColor Cyan
Write-Host "Contents: output\ (2 CSVs) + source\ (code) $(if (Test-Path $demo) {'+ demo\'} else {''})"
if ($sizeMB -gt 15) {
    Write-Host "WARNING: ZIP is over 15 MB. Make the demo video smaller." -ForegroundColor Red
} else {
    Write-Host "Size OK (<= 15 MB). Open the ZIP once to check, then upload." -ForegroundColor Green
}
