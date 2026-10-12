# Instala el servidor MCP de AutoCAD y lo registra en Claude Code (ámbito usuario).
# Uso (PowerShell, en la carpeta del proyecto):
#   powershell -ExecutionPolicy Bypass -File scripts\install.ps1
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

Write-Host "== 1/4 Buscando Python 3.10+ ==" -ForegroundColor Cyan
$py = $null
$candidates = @(
    @{ exe = "py"; pre = @("-3") },
    @{ exe = "python"; pre = @() }
)
foreach ($cand in $candidates) {
    $exe = $cand.exe
    $pre = $cand.pre
    if (-not (Get-Command $exe -ErrorAction SilentlyContinue)) { continue }
    try {
        $v = & $exe @pre -c "import sys; print(f'{sys.version_info[0]}.{sys.version_info[1]}')" 2>$null
        if ($LASTEXITCODE -eq 0 -and [version]"$v" -ge [version]"3.10") { $py = $cand; break }
    } catch {}
}
if (-not $py) {
    Write-Host "No se encontró Python 3.10 o superior." -ForegroundColor Red
    Write-Host "Instálalo desde https://www.python.org/downloads/ (marca 'Add python.exe to PATH') o con:"
    Write-Host "  winget install Python.Python.3.12"
    exit 1
}
Write-Host "Usando: $($py.exe) $($py.pre -join ' ') (Python $v)"

Write-Host "== 2/4 Creando entorno virtual .venv ==" -ForegroundColor Cyan
if (-not (Test-Path ".venv\Scripts\python.exe")) {
    $pre = $py.pre
    & $py.exe @pre -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw "No se pudo crear el entorno virtual" }
}
$VenvPy = Join-Path $Root ".venv\Scripts\python.exe"
& $VenvPy -m pip install --upgrade pip | Out-Null
& $VenvPy -m pip install -e ".[dev]"
if ($LASTEXITCODE -ne 0) { throw "Falló la instalación de dependencias" }

Write-Host "== 3/4 Comprobando dependencias ==" -ForegroundColor Cyan
& $VenvPy -c "import win32com.client, mcp; print('pywin32 y mcp OK')"
if ($LASTEXITCODE -ne 0) { throw "pywin32 o mcp no se importan correctamente" }

Write-Host "== 4/4 Registrando el servidor 'autocad' en Claude Code ==" -ForegroundColor Cyan
$claude = Get-Command claude -ErrorAction SilentlyContinue
if ($claude) {
    try { & claude mcp remove autocad --scope user 2>$null | Out-Null } catch {}
    & claude mcp add autocad --scope user -- "$VenvPy" -m autocad_mcp
    if ($LASTEXITCODE -ne 0) { throw "No se pudo registrar el servidor en Claude Code" }
    & claude mcp list
} else {
    Write-Host "No se encontró el comando 'claude'. Instala Claude Code con:" -ForegroundColor Yellow
    Write-Host "  irm https://claude.ai/install.ps1 | iex"
    Write-Host "y después ejecuta:"
    Write-Host "  claude mcp add autocad --scope user -- ""$VenvPy"" -m autocad_mcp"
}

Write-Host ""
Write-Host "Listo. Siguientes pasos:" -ForegroundColor Green
Write-Host "  1. Abre AutoCAD."
Write-Host "  2. Prueba la conexión:  .venv\Scripts\python.exe scripts\test_connection.py"
Write-Host "  3. En esta carpeta ejecuta 'claude' y pídele, por ejemplo: 'dibuja un rectángulo de 10x5'."
