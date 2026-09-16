param(
  [string]$FrontendBase = "http://127.0.0.1:3000",
  [string]$BackendBase = "http://127.0.0.1:8001"
)

$ErrorActionPreference = "Continue"

function Test-PortListening([int]$Port) {
  $line = (netstat -ano | Select-String (":$Port\s") | Select-String "LISTENING" | Select-Object -First 1)
  if ($line) {
    $parts = ($line.Line -split "\s+") | Where-Object { $_ -ne "" }
    return @{ listening = $true; pid = $parts[-1] }
  }
  return @{ listening = $false; pid = $null }
}

function Test-Url([string]$Url) {
  try {
    $resp = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 15
    return @{ ok = $true; status = $resp.StatusCode; message = "OK" }
  } catch {
    return @{ ok = $false; status = $null; message = $_.Exception.Message }
  }
}

Write-Host "== MEDQC Stack Check =="
Write-Host "Time: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
Write-Host ""

$p3000 = Test-PortListening 3000
$p8001 = Test-PortListening 8001

Write-Host "[Port] 3000 listening: $($p3000.listening) pid=$($p3000.pid)"
Write-Host "[Port] 8001 listening: $($p8001.listening) pid=$($p8001.pid)"
Write-Host ""

$backendDocs = Test-Url "$BackendBase/docs"
Write-Host "[HTTP] $BackendBase/docs => ok=$($backendDocs.ok) status=$($backendDocs.status) msg=$($backendDocs.message)"

$frontendRoot = Test-Url "$FrontendBase/"
$frontendRoute = Test-Url "$FrontendBase/workstation-v5"
Write-Host "[HTTP] $FrontendBase/ => ok=$($frontendRoot.ok) status=$($frontendRoot.status) msg=$($frontendRoot.message)"
Write-Host "[HTTP] $FrontendBase/workstation-v5 => ok=$($frontendRoute.ok) status=$($frontendRoute.status) msg=$($frontendRoute.message)"
Write-Host ""

try {
  $body = @{
    visit_id = "V-ZS-001"
    patient_id = "P-ZS-2026"
    skip_llm = $false
  } | ConvertTo-Json

  $qc = Invoke-RestMethod -Uri "$FrontendBase/api/v1/qc/coding-qc/check" -Method Post -ContentType "application/json" -Body $body -TimeoutSec 90
  $llmIssues = @($qc.data.llm_issues)
  $primary = @($llmIssues | Where-Object { $_.dimension -eq "primary" })
  Write-Host "[QC] /api/v1/qc/coding-qc/check => ok=True llm_total=$($llmIssues.Count) primary_count=$($primary.Count)"
} catch {
  Write-Host "[QC] /api/v1/qc/coding-qc/check => ok=False msg=$($_.Exception.Message)"
}
