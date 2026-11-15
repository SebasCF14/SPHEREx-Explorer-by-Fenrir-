# Ejecutar con Flask abierto en otra terminal y el entorno virtual activado.
$ErrorActionPreference = 'Stop'
$base = 'http://127.0.0.1:5000'

try {
    $health = Invoke-RestMethod "$base/api/health" -TimeoutSec 12
    Write-Host "Backend: $($health.status) | v14 radios: $($health.radius_view_enabled)" -ForegroundColor Cyan
    if (-not $health.radius_view_enabled) {
        throw "El backend abierto no parece ser v14. Deten Flask y ejecuta python .\main.py."
    }
} catch {
    Write-Host "No se pudo contactar con Flask en $base : $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

$radios = @(0.0100, 0.0150, 0.0211, 0.0300, 0.0500)
foreach ($r in $radios) {
    Write-Host "`n--- Radio $r grados: TIMELAPSE desde cache ---" -ForegroundColor Cyan
    $params = @{
        ra='17h57m48.5s'; dec='+04d41m36s'; radius=$r
        max_frames=8; fps=2; crop_size=360
        collection='spherex_dr1'; detector='ALL'; mode='timelapse'
        use_cutouts=$true; view_mode='radius'; offline_only=$true
    }
    try {
        $request = Invoke-RestMethod -Method POST "$base/api/jobs" -ContentType 'application/json' `
            -Body ($params | ConvertTo-Json -Compress) -TimeoutSec 20
        if (-not $request.job_id) { throw 'Sin identificador de trabajo' }
        $job = $null
        for ($i=0; $i -lt 150; $i++) {
            Start-Sleep -Seconds 2
            $job = Invoke-RestMethod "$base/api/jobs/$($request.job_id)" -TimeoutSec 12
            if ($job.status -in @('completed','failed')) { break }
        }
        if ($null -eq $job) { throw 'Sin respuesta del trabajo' }
        if ($job.status -eq 'completed') {
            $s=$job.summary
            Write-Host "OK | $($s.frames_generated) fotogramas | inventario: $($s.metadata_source) | cobertura visible media: $($s.visible_coverage_percent_mean)%" -ForegroundColor Green
            if ($s.coverage_warning) { Write-Host "AVISO: $($s.coverage_warning)" -ForegroundColor Yellow }
        } elseif ($job.status -eq 'failed') {
            Write-Host "FALLO: $($job.error)" -ForegroundColor Yellow
        } else {
            Write-Host 'No finalizo dentro del periodo de comprobacion.' -ForegroundColor Yellow
        }
    } catch {
        Write-Host "ERROR $r : $($_.Exception.Message)" -ForegroundColor Red
    }
}
Write-Host "`nFin de pruebas. No se borro ni modifico la cache existente." -ForegroundColor Cyan
