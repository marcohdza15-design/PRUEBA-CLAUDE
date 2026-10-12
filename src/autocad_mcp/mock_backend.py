"""Backend simulado en memoria.

Permite probar el servidor MCP sin Windows ni AutoCAD (``AUTOCAD_MCP_MOCK=1``).
Imita el formato de respuesta del backend COM, sin geometría real.
"""

from __future__ import annotations

import copy
import math
from typing import Any


def _p(p) -> list[float]:
    return (list(map(float, p)) + [0.0, 0.0, 0.0])[:3]


class MockBackend:
    name = "mock"

    def __init__(self) -> None:
        self._next = 0x100
        self.entities: dict[str, dict[str, Any]] = {}
        self.layers: dict[str, dict[str, Any]] = {
            "0": {"name": "0", "color": 7, "linetype": "Continuous", "on": True, "frozen": False, "locked": False}
        }
        self.active_layer = "0"
        self.variables: dict[str, Any] = {"INSUNITS": 4, "LTSCALE": 1.0, "CLAYER": "0"}
        self.commands: list[str] = []
        self.doc_name = "Drawing1.dwg"
        self.doc_path = ""

    def _add(self, kind: str, layer=None, color=None, **data) -> dict:
        handle = format(self._next, "X")
        self._next += 1
        if layer:
            self.create_layer(layer)
        ent = {"handle": handle, "type": kind, "layer": layer or self.active_layer,
               "color": 256 if color is None else int(color), **data}
        self.entities[handle] = ent
        return copy.deepcopy(ent)

    def _get(self, handle: str) -> dict:
        try:
            return self.entities[handle]
        except KeyError:
            raise ValueError(f"No existe ninguna entidad con handle '{handle}'") from None

    def status(self) -> dict:
        return {"connected": True, "backend": self.name, "autocad_version": "mock",
                "open_documents": [self.doc_name], "active_document": self.doc_name}

    def drawing_info(self) -> dict:
        return {"name": self.doc_name, "path": self.doc_path, "saved": False,
                "active_layer": self.active_layer, "entity_count": len(self.entities),
                "insunits": self.variables["INSUNITS"], "extmin": [0, 0, 0], "extmax": [0, 0, 0]}

    def new_drawing(self, template=None) -> dict:
        self.__init__()
        return {"name": self.doc_name}

    def open_drawing(self, path) -> dict:
        self.__init__()
        self.doc_path = path
        self.doc_name = path.replace("\\", "/").rsplit("/", 1)[-1]
        return {"name": self.doc_name, "path": path}

    def save_drawing(self, path=None) -> dict:
        if path:
            self.doc_path = path
        return {"saved": True, "path": self.doc_path}

    def draw_line(self, start, end, layer=None, color=None) -> dict:
        s, e = _p(start), _p(end)
        return self._add("AcDbLine", layer, color, start=s, end=e, length=round(math.dist(s, e), 6))

    def draw_polyline(self, points, closed=False, layer=None, color=None) -> dict:
        return self._add("AcDbPolyline", layer, color,
                         points=[[float(p[0]), float(p[1])] for p in points], closed=bool(closed))

    def draw_circle(self, center, radius, layer=None, color=None) -> dict:
        return self._add("AcDbCircle", layer, color, center=_p(center), radius=float(radius))

    def draw_arc(self, center, radius, start_angle_deg, end_angle_deg, layer=None, color=None) -> dict:
        return self._add("AcDbArc", layer, color, center=_p(center), radius=float(radius),
                         start_angle_deg=float(start_angle_deg), end_angle_deg=float(end_angle_deg))

    def draw_ellipse(self, center, major_axis_end, ratio, layer=None, color=None) -> dict:
        return self._add("AcDbEllipse", layer, color, center=_p(center))

    def draw_point(self, position, layer=None, color=None) -> dict:
        return self._add("AcDbPoint", layer, color, position=_p(position))

    def add_text(self, text, position, height, rotation_deg=0.0, layer=None, color=None) -> dict:
        return self._add("AcDbText", layer, color, text=text, insertion_point=_p(position), height=float(height))

    def add_mtext(self, text, position, width, height, layer=None, color=None) -> dict:
        return self._add("AcDbMText", layer, color, text=text, insertion_point=_p(position), height=float(height))

    def add_aligned_dimension(self, p1, p2, text_position, layer=None, color=None) -> dict:
        return self._add("AcDbAlignedDimension", layer, color)

    def add_hatch(self, boundary_handles, pattern="SOLID", scale=1.0, layer=None, color=None) -> dict:
        for h in boundary_handles:
            self._get(h)
        return self._add("AcDbHatch", layer, color)

    def insert_block(self, name_or_path, position, scale=1.0, rotation_deg=0.0, layer=None) -> dict:
        return self._add("AcDbBlockReference", layer, None, block_name=name_or_path, insertion_point=_p(position))

    def create_layer(self, name, color=None, linetype=None, make_current=False) -> dict:
        lay = self.layers.setdefault(name, {"name": name, "color": 7, "linetype": "Continuous",
                                            "on": True, "frozen": False, "locked": False})
        if color is not None:
            lay["color"] = int(color)
        if linetype:
            lay["linetype"] = linetype
        if make_current:
            self.active_layer = name
        return {k: lay[k] for k in ("name", "color", "linetype")}

    def set_current_layer(self, name) -> dict:
        if name not in self.layers:
            raise ValueError(f"La capa '{name}' no existe")
        self.active_layer = name
        return {"active_layer": name}

    def list_layers(self) -> list[dict]:
        return copy.deepcopy(list(self.layers.values()))

    def list_entities(self, layer=None, entity_type=None, limit=200) -> dict:
        items = [e for e in self.entities.values()
                 if (not layer or e["layer"].lower() == layer.lower())
                 and (not entity_type or entity_type.lower() in e["type"].lower())]
        return {"entities": copy.deepcopy(items[:limit]), "truncated": len(items) > limit,
                "model_space_count": len(self.entities)}

    def get_entity(self, handle) -> dict:
        return copy.deepcopy(self._get(handle))

    def delete_entities(self, handles) -> dict:
        for h in handles:
            self._get(h)
            del self.entities[h]
        return {"deleted": list(handles)}

    def move_entities(self, handles, from_point, to_point) -> dict:
        for h in handles:
            self._get(h)
        return {"moved": list(handles)}

    def copy_entities(self, handles, from_point, to_point) -> dict:
        new = []
        for h in handles:
            src = {k: v for k, v in self._get(h).items() if k not in ("handle", "type", "layer", "color")}
            ent = self._get(h)
            new.append(self._add(ent["type"], ent["layer"], ent["color"], **copy.deepcopy(src))["handle"])
        return {"new_handles": new}

    def rotate_entities(self, handles, base_point, angle_deg) -> dict:
        for h in handles:
            self._get(h)
        return {"rotated": list(handles)}

    def scale_entities(self, handles, base_point, factor) -> dict:
        for h in handles:
            self._get(h)
        return {"scaled": list(handles)}

    def mirror_entities(self, handles, p1, p2, delete_source=False) -> dict:
        new = self.copy_entities(handles, p1, p1)["new_handles"]
        if delete_source:
            self.delete_entities(handles)
        return {"new_handles": new}

    def offset_entity(self, handle, distance) -> dict:
        return self.copy_entities([handle], [0, 0], [0, 0])

    def set_entity_properties(self, handles, layer=None, color=None, linetype=None) -> dict:
        for h in handles:
            ent = self._get(h)
            if layer:
                self.create_layer(layer)
                ent["layer"] = layer
            if color is not None:
                ent["color"] = int(color)
        return {"updated": list(handles)}

    def zoom_extents(self) -> dict:
        return {"ok": True}

    def regen(self) -> dict:
        return {"ok": True}

    def get_variable(self, name) -> dict:
        key = name.upper()
        if key not in self.variables:
            raise ValueError(f"Variable de sistema desconocida: {name}")
        return {"name": key, "value": self.variables[key]}

    def set_variable(self, name, value) -> dict:
        self.variables[name.upper()] = value
        return {"name": name.upper(), "value": value}

    def send_command(self, command: str) -> dict:
        if not command.endswith(("\n", " ")):
            command += "\n"
        self.commands.append(command)
        return {"sent": command}
