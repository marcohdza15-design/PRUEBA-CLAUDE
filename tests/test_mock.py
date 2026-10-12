"""Pruebas del servidor con el backend simulado (no requieren Windows ni AutoCAD)."""

import os

os.environ["AUTOCAD_MCP_MOCK"] = "1"

from autocad_mcp import server  # noqa: E402


def setup_function():
    server._backend = None


def test_status_uses_mock():
    assert server.autocad_status()["backend"] == "mock"


def test_draw_and_edit_cycle():
    line = server.draw_line([0, 0], [3, 4], layer="Ejes", color=1)
    assert line["length"] == 5.0 and line["layer"] == "Ejes"
    rect = server.draw_rectangle([0, 0], [10, 5])
    assert rect["closed"] and len(rect["points"]) == 4

    copied = server.copy_entities([line["handle"]], [0, 0], [10, 0])["new_handles"]
    server.set_entity_properties(copied, color=3)
    assert server.get_entity(copied[0])["color"] == 3

    assert {l["name"] for l in server.list_layers()} == {"0", "Ejes"}
    assert len(server.list_entities(layer="Ejes")["entities"]) == 2

    server.delete_entities([line["handle"]])
    assert server.drawing_info()["entity_count"] == 2


def test_batch_reports_errors():
    out = server.execute_batch(
        [
            {"op": "create_layer", "args": {"name": "Muros", "color": 1, "make_current": True}},
            {"op": "draw_circle", "args": {"center": [0, 0], "radius": 2}},
            {"op": "delete_entities", "args": {"handles": ["FFFF"]}},
            {"op": "draw_point", "args": {"position": [1, 1]}},
        ],
        stop_on_error=True,
    )
    assert out["completed"] == 2
    assert out["results"][1]["result"]["layer"] == "Muros"
    assert not out["results"][2]["ok"] and len(out["results"]) == 3


def test_batch_rejects_unknown_op():
    try:
        server.execute_batch([{"op": "send_command", "args": {"command": "QUIT"}}])
    except server.ToolError:
        return
    raise AssertionError("debería rechazar operaciones no permitidas")
