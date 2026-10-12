"""Servidor MCP (stdio) que expone herramientas para dibujar y editar en AutoCAD."""

from __future__ import annotations

import os
import sys
from typing import Any

try:  # mcp >= 2.0
    from mcp.server.mcpserver import MCPServer as _Server
    from mcp.server.mcpserver.exceptions import ToolError
except ImportError:  # mcp 1.x
    from mcp.server.fastmcp import FastMCP as _Server
    from mcp.server.fastmcp.exceptions import ToolError

from autocad_mcp.worker import Worker

INSTRUCTIONS = """\
Herramientas para controlar AutoCAD (dibujo activo, espacio modelo).
- Coordenadas en unidades de dibujo: [x, y] o [x, y, z]. Ángulos en grados, antihorario desde +X.
- Colores: índice ACI (1 rojo, 2 amarillo, 3 verde, 4 cian, 5 azul, 6 magenta, 7 blanco/negro, 256 PorCapa).
- Cada entidad creada devuelve su 'handle'; úsalo para mover, copiar, borrar o cambiar propiedades.
- Para dibujos con muchas entidades usa execute_batch (una sola llamada).
- Llama a autocad_status primero para comprobar la conexión.
- send_command ejecuta cualquier comando/AutoLISP; úsalo solo cuando no exista una herramienta específica.
"""

mcp = _Server("autocad", instructions=INSTRUCTIONS)

_worker = Worker()
_backend: Any = None


def _create_backend() -> Any:
    if os.environ.get("AUTOCAD_MCP_MOCK", "").lower() in ("1", "true", "yes"):
        from autocad_mcp.mock_backend import MockBackend

        return MockBackend()
    if sys.platform != "win32":
        raise RuntimeError(
            "AutoCAD solo puede controlarse desde Windows. Ejecuta Claude Code y este servidor en el "
            "mismo PC donde está instalado AutoCAD (o usa AUTOCAD_MCP_MOCK=1 para pruebas)."
        )
    try:
        from autocad_mcp.com_backend import AutoCADBackend
    except ImportError as exc:
        raise RuntimeError("Falta pywin32. Instálalo con: pip install pywin32") from exc
    return AutoCADBackend()


def _get_backend() -> Any:
    global _backend
    if _backend is None:
        _backend = _create_backend()
    return _backend


def _run(fn: Any) -> Any:
    """Ejecuta fn en el hilo COM y convierte los fallos en ToolError para que Claude vea el motivo."""
    try:
        return _worker.call(fn)
    except ToolError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise ToolError(f"{type(exc).__name__}: {exc}") from exc


def _call(method: str, *args: Any, **kwargs: Any) -> Any:
    return _run(lambda: getattr(_get_backend(), method)(*args, **kwargs))


Point = list[float]


# ---------------------------------------------------------------- estado y documentos
@mcp.tool()
def autocad_status() -> dict:
    """Conecta con AutoCAD (lo abre si no está abierto) y devuelve versión y documentos abiertos."""
    return _call("status")


@mcp.tool()
def drawing_info() -> dict:
    """Información del dibujo activo: nombre, ruta, capa actual, nº de entidades, unidades y extensión."""
    return _call("drawing_info")


@mcp.tool()
def new_drawing(template: str | None = None) -> dict:
    """Crea un dibujo nuevo (opcionalmente desde una plantilla .dwt) y lo activa."""
    return _call("new_drawing", template)


@mcp.tool()
def open_drawing(path: str) -> dict:
    """Abre un archivo .dwg existente (ruta absoluta de Windows) y lo activa."""
    return _call("open_drawing", path)


@mcp.tool()
def save_drawing(path: str | None = None) -> dict:
    """Guarda el dibujo activo. Si se indica 'path' (.dwg absoluto) hace 'Guardar como'."""
    return _call("save_drawing", path)


# ---------------------------------------------------------------- dibujo
@mcp.tool()
def draw_line(start: Point, end: Point, layer: str | None = None, color: int | None = None) -> dict:
    """Dibuja una línea entre dos puntos."""
    return _call("draw_line", start, end, layer, color)


@mcp.tool()
def draw_polyline(points: list[Point], closed: bool = False, layer: str | None = None,
                  color: int | None = None) -> dict:
    """Dibuja una polilínea 2D (LWPOLYLINE) por la lista de puntos [[x, y], ...]."""
    return _call("draw_polyline", points, closed, layer, color)


@mcp.tool()
def draw_rectangle(corner1: Point, corner2: Point, layer: str | None = None, color: int | None = None) -> dict:
    """Dibuja un rectángulo (polilínea cerrada) a partir de dos esquinas opuestas."""
    (x1, y1), (x2, y2) = corner1[:2], corner2[:2]
    pts = [[x1, y1], [x2, y1], [x2, y2], [x1, y2]]
    return _call("draw_polyline", pts, True, layer, color)


@mcp.tool()
def draw_circle(center: Point, radius: float, layer: str | None = None, color: int | None = None) -> dict:
    """Dibuja un círculo."""
    return _call("draw_circle", center, radius, layer, color)


@mcp.tool()
def draw_arc(center: Point, radius: float, start_angle_deg: float, end_angle_deg: float,
             layer: str | None = None, color: int | None = None) -> dict:
    """Dibuja un arco (antihorario desde start_angle_deg hasta end_angle_deg)."""
    return _call("draw_arc", center, radius, start_angle_deg, end_angle_deg, layer, color)


@mcp.tool()
def draw_ellipse(center: Point, major_axis_end: Point, ratio: float, layer: str | None = None,
                 color: int | None = None) -> dict:
    """Dibuja una elipse. major_axis_end es el vector del semieje mayor RELATIVO al centro; ratio = menor/mayor."""
    return _call("draw_ellipse", center, major_axis_end, ratio, layer, color)


@mcp.tool()
def draw_point(position: Point, layer: str | None = None, color: int | None = None) -> dict:
    """Dibuja un punto."""
    return _call("draw_point", position, layer, color)


@mcp.tool()
def add_text(text: str, position: Point, height: float, rotation_deg: float = 0.0,
             layer: str | None = None, color: int | None = None) -> dict:
    """Añade texto de una línea (TEXT) con su punto de inserción y altura."""
    return _call("add_text", text, position, height, rotation_deg, layer, color)


@mcp.tool()
def add_mtext(text: str, position: Point, width: float, height: float, layer: str | None = None,
              color: int | None = None) -> dict:
    """Añade texto de varias líneas (MTEXT). 'position' es la esquina superior izquierda."""
    return _call("add_mtext", text, position, width, height, layer, color)


@mcp.tool()
def add_aligned_dimension(p1: Point, p2: Point, text_position: Point, layer: str | None = None,
                          color: int | None = None) -> dict:
    """Añade una cota alineada entre p1 y p2; text_position indica dónde va la línea de cota."""
    return _call("add_aligned_dimension", p1, p2, text_position, layer, color)


@mcp.tool()
def add_hatch(boundary_handles: list[str], pattern: str = "SOLID", scale: float = 1.0,
              layer: str | None = None, color: int | None = None) -> dict:
    """Sombrea el área delimitada por entidades cerradas (handles). Patrones: SOLID, ANSI31, ANSI37, AR-CONC..."""
    return _call("add_hatch", boundary_handles, pattern, scale, layer, color)


@mcp.tool()
def insert_block(name_or_path: str, position: Point, scale: float = 1.0, rotation_deg: float = 0.0,
                 layer: str | None = None) -> dict:
    """Inserta un bloque existente en el dibujo, o un archivo .dwg externo como bloque (ruta absoluta)."""
    return _call("insert_block", name_or_path, position, scale, rotation_deg, layer)


# ---------------------------------------------------------------- capas
@mcp.tool()
def create_layer(name: str, color: int | None = None, linetype: str | None = None,
                 make_current: bool = False) -> dict:
    """Crea (o actualiza) una capa con color ACI y tipo de línea (p. ej. DASHED, CENTER, HIDDEN)."""
    return _call("create_layer", name, color, linetype, make_current)


@mcp.tool()
def set_current_layer(name: str) -> dict:
    """Establece la capa actual."""
    return _call("set_current_layer", name)


@mcp.tool()
def list_layers() -> list[dict]:
    """Lista las capas del dibujo con color, tipo de línea y estado."""
    return _call("list_layers")


# ---------------------------------------------------------------- consulta y edición
@mcp.tool()
def list_entities(layer: str | None = None, entity_type: str | None = None, limit: int = 200) -> dict:
    """Lista entidades del espacio modelo, filtrando opcionalmente por capa o tipo (p. ej. 'Line', 'Circle')."""
    return _call("list_entities", layer, entity_type, limit)


@mcp.tool()
def get_entity(handle: str) -> dict:
    """Devuelve las propiedades y geometría de una entidad por su handle."""
    return _call("get_entity", handle)


@mcp.tool()
def delete_entities(handles: list[str]) -> dict:
    """Borra las entidades indicadas."""
    return _call("delete_entities", handles)


@mcp.tool()
def move_entities(handles: list[str], from_point: Point, to_point: Point) -> dict:
    """Desplaza entidades según el vector from_point -> to_point."""
    return _call("move_entities", handles, from_point, to_point)


@mcp.tool()
def copy_entities(handles: list[str], from_point: Point, to_point: Point) -> dict:
    """Copia entidades desplazadas según el vector from_point -> to_point. Devuelve los nuevos handles."""
    return _call("copy_entities", handles, from_point, to_point)


@mcp.tool()
def rotate_entities(handles: list[str], base_point: Point, angle_deg: float) -> dict:
    """Gira entidades alrededor de base_point (grados, antihorario)."""
    return _call("rotate_entities", handles, base_point, angle_deg)


@mcp.tool()
def scale_entities(handles: list[str], base_point: Point, factor: float) -> dict:
    """Escala entidades respecto a base_point."""
    return _call("scale_entities", handles, base_point, factor)


@mcp.tool()
def mirror_entities(handles: list[str], p1: Point, p2: Point, delete_source: bool = False) -> dict:
    """Crea la simetría de entidades respecto al eje p1-p2."""
    return _call("mirror_entities", handles, p1, p2, delete_source)


@mcp.tool()
def offset_entity(handle: str, distance: float) -> dict:
    """Desfase (OFFSET) de líneas, arcos, círculos o polilíneas. Distancia negativa = hacia el otro lado."""
    return _call("offset_entity", handle, distance)


@mcp.tool()
def set_entity_properties(handles: list[str], layer: str | None = None, color: int | None = None,
                          linetype: str | None = None) -> dict:
    """Cambia capa, color ACI o tipo de línea de las entidades indicadas."""
    return _call("set_entity_properties", handles, layer, color, linetype)


# ---------------------------------------------------------------- lotes
BATCH_OPERATIONS = {
    "draw_line", "draw_polyline", "draw_circle", "draw_arc", "draw_ellipse", "draw_point",
    "add_text", "add_mtext", "add_aligned_dimension", "add_hatch", "insert_block",
    "create_layer", "set_current_layer", "move_entities", "copy_entities", "rotate_entities",
    "scale_entities", "mirror_entities", "offset_entity", "set_entity_properties", "delete_entities",
}


@mcp.tool()
def execute_batch(operations: list[dict[str, Any]], stop_on_error: bool = True) -> dict:
    """Ejecuta muchas operaciones en una sola llamada (mucho más rápido para dibujos grandes).

    Cada operación: {"op": "<nombre>", "args": {...}} con los mismos argumentos que la herramienta
    homónima. Operaciones válidas: draw_line, draw_polyline, draw_circle, draw_arc, draw_ellipse,
    draw_point, add_text, add_mtext, add_aligned_dimension, add_hatch, insert_block, create_layer,
    set_current_layer, move_entities, copy_entities, rotate_entities, scale_entities, mirror_entities,
    offset_entity, set_entity_properties, delete_entities. (Para rectángulos usa draw_polyline cerrada.)
    """
    for i, op in enumerate(operations):
        if op.get("op") not in BATCH_OPERATIONS:
            raise ToolError(f"Operación {i}: '{op.get('op')}' no es válida en un lote")

    def run() -> dict:
        backend = _get_backend()
        results: list[dict[str, Any]] = []
        for i, op in enumerate(operations):
            try:
                results.append({"index": i, "ok": True, "result": getattr(backend, op["op"])(**op.get("args", {}))})
            except Exception as exc:  # noqa: BLE001 - se informa al cliente
                results.append({"index": i, "ok": False, "error": str(exc)})
                if stop_on_error:
                    break
        return {"completed": sum(r["ok"] for r in results), "total": len(operations), "results": results}

    return _run(run)


# ---------------------------------------------------------------- vista y sistema
@mcp.tool()
def zoom_extents() -> dict:
    """Hace zoom para mostrar todo el dibujo."""
    return _call("zoom_extents")


@mcp.tool()
def regen() -> dict:
    """Regenera el dibujo en todas las ventanas."""
    return _call("regen")


@mcp.tool()
def get_variable(name: str) -> dict:
    """Lee una variable de sistema de AutoCAD (p. ej. INSUNITS, LTSCALE, DIMSCALE, OSMODE)."""
    return _call("get_variable", name)


@mcp.tool()
def set_variable(name: str, value: Any) -> dict:
    """Modifica una variable de sistema de AutoCAD (el valor se convierte al tipo de la variable)."""
    return _call("set_variable", name, value)


@mcp.tool()
def send_command(command: str) -> dict:
    """Envía texto a la línea de comandos de AutoCAD, como si se tecleara (comandos o expresiones AutoLISP).

    Usa la versión de línea de comandos (con guion) para evitar cuadros de diálogo, p. ej.
    '-LAYER M Muros C 1  ' o '(command "_.FILLET" ...)'. Se ejecuta de forma asíncrona:
    no devuelve el resultado; consulta después con list_entities/drawing_info.
    """
    return _call("send_command", command)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
