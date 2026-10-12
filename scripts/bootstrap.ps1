# Instalacion completa en un paso (Windows). Ejecutar en PowerShell:
#   irm https://raw.githubusercontent.com/marcohdza15-design/PRUEBA-CLAUDE/claude/autocad-mcp-integration-io4zvf/scripts/bootstrap.ps1 | iex
#
# Instala lo que falte (Git, Python 3.12, Claude Code), descarga este proyecto en
# %USERPROFILE%\autocad-mcp, crea su entorno de Python y registra el servidor MCP
# "autocad" en Claude Code.

& {
$ErrorActionPreference = "Stop"
$Repo = "marcohdza15-design/PRUEBA-CLAUDE"
$Branch = "claude/autocad-mcp-integration-io4zvf"
$Dest = Join-Path $env:USERPROFILE "autocad-mcp"

function Step($msg) { Write-Host "`n== $msg ==" -ForegroundColor Cyan }
function Refresh-Path {
    $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" +
                [Environment]::GetEnvironmentVariable("Path", "User") + ";" +
                (Join-Path $env:USERPROFILE ".local\bin")
}
function Has($cmd) { [bool](Get-Command $cmd -ErrorAction SilentlyContinue) }
function Winget-Install($id) {
    if (-not (Has "winget")) {
        throw "No esta disponible 'winget'. Instala 'App Installer' desde Microsoft Store y vuelve a ejecutar."
    }
    winget install -e --id $id --scope user --accept-package-agreements --accept-source-agreements --silent
    if ($LASTEXITCODE -ne 0) {
        # Algunos paquetes no admiten --scope user
        winget install -e --id $id --accept-package-agreements --accept-source-agreements --silent
    }
    Refresh-Path
}
function Python-Ok {
    foreach ($c in @(@{e = "py"; a = @("-3")}, @{e = "python"; a = @()})) {
        if (-not (Has $c.e)) { continue }
        try {
            $a = $c.a
            $v = & $c.e @a -c "import sys; print(f'{sys.version_info[0]}.{sys.version_info[1]}')" 2>$null
            if ($LASTEXITCODE -eq 0 -and [version]"$v" -ge [version]"3.10") { return $true }
        } catch {}
    }
    return $false
}

Step "1/6 Comprobando AutoCAD"
if (Test-Path "Registry::HKEY_CLASSES_ROOT\AutoCAD.Application") {
    Write-Host "AutoCAD (con API COM) detectado."
} else {
    Write-Host "AVISO: no se detecto AutoCAD con API COM. AutoCAD LT no es compatible." -ForegroundColor Yellow
    Write-Host "La instalacion continua, pero necesitaras AutoCAD completo para usarlo."
}

Step "2/6 Git"
Refresh-Path
if (Has "git") { Write-Host "Git ya instalado." } else { Winget-Install "Git.Git" }

Step "3/6 Python 3.10+"
if (Python-Ok) { Write-Host "Python ya instalado." } else {
    Winget-Install "Python.Python.3.12"
    if (-not (Python-Ok)) { throw "Python se instalo pero no se encuentra. Cierra y abre PowerShell y vuelve a ejecutar el comando." }
}

Step "4/6 Claude Code"
if (Has "claude") { Write-Host "Claude Code ya instalado." } else {
    # En un proceso aparte: si el instalador oficial llama a 'exit' no cierra esta ventana.
    & powershell -NoProfile -ExecutionPolicy Bypass -Command "irm https://claude.ai/install.ps1 | iex"
    Refresh-Path
    if (-not (Has "claude")) { throw "Claude Code se instalo pero no se encuentra. Cierra y abre PowerShell y vuelve a ejecutar el comando." }
}

Step "5/6 Descargando el proyecto en $Dest"
$tmp = Join-Path $env:TEMP ("autocad-mcp-" + [guid]::NewGuid())
New-Item -ItemType Directory -Path $tmp | Out-Null
$zip = Join-Path $tmp "src.zip"
Invoke-WebRequest -UseBasicParsing "https://github.com/$Repo/archive/refs/heads/$Branch.zip" -OutFile $zip
Expand-Archive $zip -DestinationPath $tmp
$src = Get-ChildItem $tmp -Directory | Select-Object -First 1
# robocopy fusiona con una instalacion previa (conserva .venv); codigos < 8 = exito
robocopy $src.FullName $Dest /E /NFL /NDL /NJH /NJS /NP | Out-Null
if ($LASTEXITCODE -ge 8) { throw "No se pudieron copiar los archivos a $Dest" }
Remove-Item $tmp -Recurse -Force

Step "6/6 Instalando dependencias y registrando el servidor MCP"
& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $Dest "scripts\install.ps1")
if ($LASTEXITCODE -ne 0) { throw "Fallo scripts\install.ps1 (revisa los mensajes de arriba)." }

Write-Host "`nTODO LISTO." -ForegroundColor Green
Write-Host "1. Abre AutoCAD."
Write-Host "2. Prueba:   cd `"$Dest`"; .venv\Scripts\python.exe scripts\test_connection.py"
Write-Host "3. Usa Claude:   cd `"$Dest`"; claude   (la primera vez te pedira iniciar sesion)"
}
