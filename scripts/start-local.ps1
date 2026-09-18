param([switch]$SkipPull)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
$pythonPath = Join-Path $projectRoot '.venv\Scripts\python.exe'
$ollamaPath = Join-Path $projectRoot '.local\ollama\ollama.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw 'Create .venv and install requirements first; see README.md.'
}
if (-not (Test-Path -LiteralPath $ollamaPath)) {
    & $pythonPath scripts/install_ollama.py
    if ($LASTEXITCODE -ne 0) { throw 'Ollama download failed.' }
}
$env:OLLAMA_MODELS = Join-Path $projectRoot '.local\models'
$env:OLLAMA_HOST = '127.0.0.1:11434'
$env:OLLAMA_VULKAN = '1'
$logRoot = Join-Path $projectRoot '.local'
$running = $false
try {
    $null = Invoke-RestMethod 'http://127.0.0.1:11434/api/tags' -TimeoutSec 2
    $running = $true
} catch {}
if (-not $running) {
    $process = Start-Process -FilePath $ollamaPath -ArgumentList 'serve' -WindowStyle Hidden -PassThru -RedirectStandardOutput "$logRoot\ollama.out.log" -RedirectStandardError "$logRoot\ollama.err.log"
    $process.Id | Set-Content "$logRoot\ollama.pid"
    for ($attempt = 0; $attempt -lt 30; $attempt++) {
        try {
            $null = Invoke-RestMethod 'http://127.0.0.1:11434/api/tags' -TimeoutSec 2
            $running = $true
            break
        } catch { Start-Sleep -Seconds 1 }
    }
    if (-not $running) { throw 'Ollama did not become ready. Check .local/ollama.err.log.' }
}
if (-not $SkipPull) {
    & $ollamaPath pull 'qwen3:4b-instruct'
    if ($LASTEXITCODE -ne 0) { throw 'Model download failed. Rerun this script to resume.' }
}
Write-Host 'Warming the free local model...'
& $pythonPath scripts/warm_model.py
if ($LASTEXITCODE -ne 0) { throw 'Model warmup failed.' }
Write-Host 'Starting GridWise at http://127.0.0.1:8000/docs. Ctrl+C stops the API.'
& $pythonPath -m gridwise
