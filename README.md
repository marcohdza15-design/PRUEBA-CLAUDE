# AutoCAD MCP para Claude Code

Servidor [MCP](https://modelcontextprotocol.io) que permite a **Claude Code** dibujar y
editar en **AutoCAD** a partir de instrucciones en lenguaje natural:

> «Crea una capa Muros en rojo y dibuja una habitación de 4×3 m con muros de 15 cm,
> una puerta de 90 cm en el lado sur y acótala.»

```
Claude Code  ──(MCP / stdio)──>  autocad_mcp (Python)  ──(ActiveX/COM)──>  AutoCAD
```

## Requisitos

| Requisito | Notas |
|---|---|
| Windows 10/11 | La automatización COM de AutoCAD solo existe en Windows. |
| **AutoCAD completo** (2018 o posterior) o verticales (Architecture, Civil 3D, Mechanical...) | **AutoCAD LT no sirve**: no tiene API ActiveX/COM. Tampoco AutoCAD para Mac. |
| Python 3.10+ | `winget install Python.Python.3.12` o https://www.python.org/downloads/ (marca *Add python.exe to PATH*). |
| Claude Code | `irm https://claude.ai/install.ps1 \| iex` en PowerShell (ver [documentación](https://code.claude.com/docs)). |

> Claude Code debe ejecutarse **en el mismo PC que AutoCAD** (no en la nube), porque
> el servidor MCP se comunica con la instancia local de AutoCAD.

## Instalación en un solo paso (recomendada)

Abre **PowerShell** (tecla Windows → escribe *PowerShell* → Enter), pega este comando y pulsa Enter:

```powershell
irm https://raw.githubusercontent.com/marcohdza15-design/PRUEBA-CLAUDE/claude/autocad-mcp-integration-io4zvf/scripts/bootstrap.ps1 | iex
```

Instala lo que falte (Git, Python 3.12, Claude Code), descarga el proyecto en
`%USERPROFILE%\autocad-mcp`, crea el entorno de Python y registra el servidor `autocad`
en Claude Code. Puede que Windows pida permiso (UAC) para instalar Git o Python: acéptalo.
Si al final indica que cierres y abras PowerShell, hazlo y vuelve a pegar el mismo comando
(es seguro repetirlo). Después sigue desde el paso 3 de abajo, usando la carpeta
`%USERPROFILE%\autocad-mcp`.

## Instalación paso a paso

1. **Descarga el proyecto**
   - Con Git: `git clone https://github.com/marcohdza15-design/prueba-claude.git`
     y `git checkout claude/autocad-mcp-integration-io4zvf`
   - O en GitHub: selecciona la rama `claude/autocad-mcp-integration-io4zvf` →
     botón **Code → Download ZIP** y descomprímelo (p. ej. en `C:\autocad-mcp`).

2. **Ejecuta el instalador**: doble clic en `scripts\install.bat`
   (o en PowerShell: `powershell -ExecutionPolicy Bypass -File scripts\install.ps1`).
   El instalador:
   - crea un entorno virtual `.venv` e instala `mcp` y `pywin32`;
   - registra el servidor en Claude Code con
     `claude mcp add autocad --scope user -- <ruta>\.venv\Scripts\python.exe -m autocad_mcp`
     (queda disponible desde cualquier carpeta).

3. **Prueba la conexión** con AutoCAD abierto:
   ```powershell
   .venv\Scripts\python.exe scripts\test_connection.py
   ```
   Debe aparecer una línea, un círculo y un texto en la capa `MCP_TEST`.

4. **Usa Claude Code**: abre una terminal en la carpeta del proyecto y ejecuta `claude`.
   Comprueba con `/mcp` que el servidor `autocad` aparece como *connected*.

> Abrir `claude` dentro de esta carpeta carga también `CLAUDE.md` (buenas prácticas de
> dibujo para Claude) y `.claude/settings.json` (permite las herramientas de dibujo sin
> preguntar cada vez; `send_command`, abrir, crear y guardar dibujos siguen pidiendo permiso).

### Instalación manual (alternativa)

```powershell
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install -e .
claude mcp add autocad --scope user -- "C:\ruta\al\proyecto\.venv\Scripts\python.exe" -m autocad_mcp
```

O añade la configuración a un `.mcp.json` en tu proyecto (ver `.mcp.json.example`).

## Ejemplos de peticiones

- «Dime qué hay en el dibujo actual y en qué unidades está.»
- «Dibuja la planta de una casa de 10×8 m con 3 habitaciones, muros de 15 cm en la capa
  Muros (rojo), ejes en la capa Ejes con línea CENTER y cotas generales.»
- «Dibuja una brida circular de 200 mm de diámetro con 8 agujeros de 18 mm en un
  círculo de 160 mm.»
- «Pasa todos los círculos de la capa 0 a la capa Taladros y ponlos en azul.»
- «Haz una simetría de todo lo de la capa Mobiliario respecto al eje x = 5000.»
- «Sombrea con ANSI31 el rectángulo que acabas de dibujar.»
- «Ejecuta un FILLET de radio 10 entre las dos últimas líneas.» (usa `send_command`)
- «Guarda el dibujo como C:\Proyectos\planta.dwg.»

## Herramientas disponibles

| Grupo | Herramientas |
|---|---|
| Estado / archivos | `autocad_status`, `drawing_info`, `new_drawing`, `open_drawing`, `save_drawing` |
| Dibujo | `draw_line`, `draw_polyline`, `draw_rectangle`, `draw_circle`, `draw_arc`, `draw_ellipse`, `draw_point`, `add_text`, `add_mtext`, `add_aligned_dimension`, `add_hatch`, `insert_block` |
| Capas | `create_layer`, `set_current_layer`, `list_layers` |
| Consulta / edición | `list_entities`, `get_entity`, `delete_entities`, `move_entities`, `copy_entities`, `rotate_entities`, `scale_entities`, `mirror_entities`, `offset_entity`, `set_entity_properties` |
| Lotes | `execute_batch` (muchas operaciones en una sola llamada) |
| Vista / sistema | `zoom_extents`, `regen`, `get_variable`, `set_variable`, `send_command` (cualquier comando o AutoLISP) |

## Configuración opcional

| Variable de entorno | Uso |
|---|---|
| `AUTOCAD_PROGID` | Forzar una versión concreta si tienes varias instaladas, p. ej. `AutoCAD.Application.25` (2025), `.24.3` (2024), `.24.2` (2023), `.24.1` (2022). |
| `AUTOCAD_MCP_MOCK=1` | Backend simulado en memoria, para probar sin AutoCAD. |

Ejemplo: `claude mcp add autocad --scope user -e AUTOCAD_PROGID=AutoCAD.Application.25 -- <python> -m autocad_mcp`

## Solución de problemas

| Síntoma | Causa / solución |
|---|---|
| `/mcp` muestra *failed* | Ejecuta a mano `.venv\Scripts\python.exe -m autocad_mcp`: no debe mostrar errores (se queda esperando; cierra con Ctrl+C). Revisa que la ruta registrada en `claude mcp list` sea correcta. |
| «No se pudo conectar ni iniciar AutoCAD» | AutoCAD no está instalado, es LT, o el ProgID no coincide (usa `AUTOCAD_PROGID`). |
| Funciona `test_connection.py` pero no desde Claude, o se abre un segundo AutoCAD | AutoCAD y la terminal de Claude deben tener el **mismo nivel de privilegios**: no ejecutes uno como administrador y el otro no. |
| «Call was rejected by callee» persistente | AutoCAD está ocupado: cierra cuadros de diálogo abiertos o pulsa Esc en la línea de comandos. El servidor reintenta automáticamente unos 10 s. |
| `send_command` no hace nada | Es asíncrono y requiere que AutoCAD no esté en medio de otro comando; usa la versión con guion del comando (`-LAYER`, `-HATCH`...). |
| Error al importar `win32com` | Reinstala: `.venv\Scripts\python.exe -m pip install --force-reinstall pywin32`. |

## Desarrollo

```bash
pip install -e ".[dev]"
AUTOCAD_MCP_MOCK=1 pytest     # pruebas sin AutoCAD (en Linux/macOS también)
```

Estructura:

```
src/autocad_mcp/
  server.py        # definición de herramientas MCP
  com_backend.py   # implementación real (pywin32 / ActiveX)
  mock_backend.py  # implementación simulada para pruebas
  worker.py        # hilo único con COM inicializado
scripts/
  bootstrap.ps1               # instalación completa en un paso (irm ... | iex)
  install.ps1 / install.bat   # instalador para Windows
  test_connection.py          # prueba directa contra AutoCAD
tests/test_mock.py
CLAUDE.md                     # instrucciones de uso para Claude
.claude/settings.json         # permisos de las herramientas
```
