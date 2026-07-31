param(
  [string]$VisitId,
  [string]$VisitIdFile,
  [string]$OutputDir = "D:\medqc\sample_export",
  [string]$RemoteHost = "192.168.140.160",
  [int]$RemotePort = 16016,
  [string]$Database = "clinical_data",
  [string]$Username = "postgres",
  [string]$Password = "",
  [string]$RemoteSchema = "public",
  [string]$PsqlPath = "C:\Program Files\PostgreSQL\16\bin\psql.exe"
)

$ErrorActionPreference = "Stop"

function Write-Step([string]$message) {
  Write-Host "[export] $message" -ForegroundColor Cyan
}

function Quote-SqlLiteral([string]$value) {
  return "'" + ($value -replace "'", "''") + "'"
}

function Normalize-VisitIds {
  $items = New-Object System.Collections.Generic.List[string]
  if ($VisitId) {
    $trimmed = $VisitId.Trim()
    if ($trimmed) {
      $items.Add($trimmed)
    }
  }
  if ($VisitIdFile) {
    if (-not (Test-Path -LiteralPath $VisitIdFile)) {
      throw "visit_id 文件不存在: $VisitIdFile"
    }
    Get-Content -LiteralPath $VisitIdFile -Encoding UTF8 | ForEach-Object {
      $trimmed = [string]$_
      if ($trimmed) {
        $trimmed = $trimmed.Trim()
      }
      if ($trimmed) {
        $items.Add($trimmed)
      }
    }
  }
  $seen = @{}
  $ordered = New-Object System.Collections.Generic.List[string]
  foreach ($item in $items) {
    if (-not $seen.ContainsKey($item)) {
      $seen[$item] = $true
      $ordered.Add($item)
    }
  }
  return $ordered
}

function Invoke-PsqlScalar([string]$sql) {
  $args = @(
    "-h", $RemoteHost,
    "-p", "$RemotePort",
    "-U", $Username,
    "-d", $Database,
    "-At",
    "-c", $sql
  )
  return (& $PsqlPath @args).Trim()
}

function Test-RemoteTable([string]$schemaName, [string]$tableName) {
  $sql = @"
select 1
from information_schema.columns
where table_schema = $(Quote-SqlLiteral $schemaName)
  and table_name = $(Quote-SqlLiteral $tableName)
  and column_name = 'visit_id'
limit 1;
"@
  $result = Invoke-PsqlScalar $sql
  return $result -eq "1"
}

function Export-TableCsv([string]$schemaName, [string]$tableName, [string[]]$visitIds, [string]$outputPath) {
  $visitSql = ($visitIds | ForEach-Object { Quote-SqlLiteral $_ }) -join ", "
  $psqlOutputPath = $outputPath.Replace("\", "/")
  $copySql = "\\copy (SELECT * FROM `"$schemaName`".`"$tableName`" WHERE CAST(visit_id AS text) IN ($visitSql)) TO '$psqlOutputPath' WITH CSV HEADER"
  $args = @(
    "-h", $RemoteHost,
    "-p", "$RemotePort",
    "-U", $Username,
    "-d", $Database,
    "-c", $copySql
  )
  & $PsqlPath @args
}

if (-not (Test-Path -LiteralPath $PsqlPath)) {
  throw "psql 不存在: $PsqlPath"
}

$resolvedVisitIds = Normalize-VisitIds
if ($resolvedVisitIds.Count -eq 0) {
  throw "请提供 -VisitId 或 -VisitIdFile"
}

if ($Password) {
  $env:PGPASSWORD = $Password
}

$tableNames = @(
  "mr",
  "inpat_registration",
  "diagnosis",
  "mr_surgery",
  "mr_cost",
  "medical_insurance_settlement",
  "medical_insurance_settlement_cost",
  "admission_record",
  "discharge_record",
  "death_record",
  "first_course_record",
  "daily_course_record",
  "senior_course_record",
  "rescue_record",
  "diffcase_discussion_record",
  "death_discussion",
  "consultation_record",
  "handoff_record",
  "handover_record",
  "docpat_commu_record",
  "summary_record",
  "surgery_record",
  "presurg_summary",
  "presurg_discussion",
  "postsurg_firstcourse_record",
  "surgery_safecheck_record",
  "surgery_risk_assessment",
  "anesthesia_record",
  "postane_surveil_record",
  "newborn_record",
  "bloodtrans_record",
  "blood_application",
  "crisis_value_record",
  "nursing_record",
  "admission_record_diagnosis",
  "discharge_record_diagnosis",
  "first_course_record_diagnosis",
  "mr_diagnosis",
  "inpat_drug_order",
  "inpat_nondrug_order",
  "inpat_prescription",
  "inpat_prescription_item",
  "inpat_bill_item",
  "exam_master",
  "exam_item_report",
  "labtest_master",
  "labtest_item_report",
  "pathology_exam_master",
  "pathology_exam_report",
  "surgery_application",
  "surgery_inform_consent",
  "surgery_inventory_record",
  "preane_surveil_record",
  "preane_surveil_record_diagnosis",
  "daily_admission_record",
  "daily_admission_record_diagnosis",
  "daily_death_record",
  "daily_death_record_diagnosis",
  "transfer_in_record",
  "transfer_out_record",
  "transfer_in_record_diagnosis",
  "transfer_out_record_diagnosis"
)

$visitTag = if ($resolvedVisitIds.Count -eq 1) { $resolvedVisitIds[0] } else { "batch_$($resolvedVisitIds.Count)" }
$safeVisitTag = ($visitTag -replace '[^0-9A-Za-z_-]', '_')
$targetDir = Join-Path $OutputDir "visit_export_$safeVisitTag"
New-Item -ItemType Directory -Force -Path $targetDir | Out-Null

$visitFile = Join-Path $targetDir "visit_ids.txt"
$resolvedVisitIds | Set-Content -LiteralPath $visitFile -Encoding UTF8

$manifest = [ordered]@{
  remote_host = $RemoteHost
  remote_port = $RemotePort
  database = $Database
  schema = $RemoteSchema
  visit_ids = @($resolvedVisitIds)
  exported_tables = @()
  skipped_tables = @()
}

Write-Step "输出目录: $targetDir"
Write-Step "visit_id 数量: $($resolvedVisitIds.Count)"

foreach ($tableName in $tableNames) {
  if (-not (Test-RemoteTable -schemaName $RemoteSchema -tableName $tableName)) {
    Write-Host "[skip] $RemoteSchema.$tableName 缺少表或 visit_id 列" -ForegroundColor Yellow
    $manifest.skipped_tables += "$RemoteSchema.$tableName"
    continue
  }
  $outFile = Join-Path $targetDir "$RemoteSchema.$tableName.csv"
  Write-Step "导出 $RemoteSchema.$tableName -> $outFile"
  Export-TableCsv -schemaName $RemoteSchema -tableName $tableName -visitIds $resolvedVisitIds -outputPath $outFile
  $manifest.exported_tables += "$RemoteSchema.$tableName"
}

$manifestPath = Join-Path $targetDir "manifest.json"
$manifest | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $manifestPath -Encoding UTF8

Write-Step "导出完成"
Write-Host $targetDir
