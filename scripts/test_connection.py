"""Prueba directa (sin Claude) de la conexión con AutoCAD.

Uso:  .venv\\Scripts\\python.exe scripts\\test_connection.py
Dibuja una línea, un círculo y un texto en la capa MCP_TEST y hace zoom.
"""

import json
import sys

if sys.platform != "win32":
    sys.exit("Este script debe ejecutarse en Windows, en el PC donde está instalado AutoCAD.")

import pythoncom

from autocad_mcp.com_backend import AutoCADBackend

pythoncom.CoInitialize()
acad = AutoCADBackend()
print("Conectando con AutoCAD (si no está abierto se iniciará, puede tardar)...")
print(json.dumps(acad.status(), indent=2, ensure_ascii=False))
acad.create_layer("MCP_TEST", color=3)
print(json.dumps(acad.draw_line([0, 0], [100, 50], layer="MCP_TEST"), ensure_ascii=False))
print(json.dumps(acad.draw_circle([50, 25], 20, layer="MCP_TEST"), ensure_ascii=False))
print(json.dumps(acad.add_text("Hola desde MCP", [0, -10], 5, layer="MCP_TEST"), ensure_ascii=False))
acad.zoom_extents()
print("\nOK: revisa AutoCAD, debería verse una línea, un círculo y un texto en verde (capa MCP_TEST).")
