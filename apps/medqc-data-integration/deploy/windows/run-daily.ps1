$ErrorActionPreference = "Stop"

$InstallRoot = "C:\Program Files\MedQC\ingest"
$Command = Join-Path $InstallRoot "Scripts\medqc-ingest.exe"
$RunDate = Get-Date -Format "yyyy-MM-dd"

& $Command extract --interface web.mr --date $RunDate --mode incremental
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

& $Command publish --interface web.mr
exit $LASTEXITCODE
