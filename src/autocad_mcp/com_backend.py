"""Backend real: controla AutoCAD (Windows) por ActiveX/COM usando pywin32.

Todas las llamadas COM deben ejecutarse en un mismo hilo que haya llamado a
CoInitialize; de eso se encarga ``ComWorker`` en ``worker.py``.
"""

from __future__ import annotations

import functools
import math
import os
import time
from typing import Any, Callable, Sequence

import pythoncom
import win32com.client
from win32com.client import VARIANT

# AutoCAD rechaza llamadas mientras está ocupado (comando activo, cuadro de
# diálogo abierto, regenerando...). Estos HRESULT indican "reintenta luego".
_RETRYABLE_HRESULTS = {
    -2147418111,  # RPC_E_CALL_REJECTED
    -2147417846,  # RPC_E_SERVERCALL_RETRYLATER
    -2147417848,  # RPC_E_DISCONNECTED (se reconecta en el siguiente intento)
}

DEFAULT_PROGID = "AutoCAD.Application"


def _retry(fn: Callable) -> Callable:
    @functools.wraps(fn)
    def wrapper(self: "AutoCADBackend", *args, **kwargs):
        attempts = 20
        for i in range(attempts):
            try:
                return fn(self, *args, **kwargs)
            except pythoncom.com_error as exc:
                if exc.hresult not in _RETRYABLE_HRESULTS or i == attempts - 1:
                    raise RuntimeError(_describe_com_error(exc)) from exc
                if exc.hresult == -2147417848:
                    self._app = None
                time.sleep(0.5)
        raise AssertionError("unreachable")

    return wrapper


def _describe_com_error(exc: pythoncom.com_error) -> str:
    detail = ""
    if exc.excepinfo and exc.excepinfo[2]:
        detail = f": {exc.excepinfo[2]}"
    return f"Error COM de AutoCAD ({exc.hresult}) {exc.strerror}{detail}"


def _pt(p: Sequence[float]) -> VARIANT:
    x, y, z = (list(map(float, p)) + [0.0, 0.0, 0.0])[:3]
    return VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, (x, y, z))


def _doubles(values: Sequence[float]) -> VARIANT:
    return VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, tuple(float(v) for v in values))


def _objects(objs: Sequence[Any]) -> VARIANT:
    return VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_DISPATCH, tuple(objs))


def _tuple(v: Any) -> list[float]:
    return [round(float(c), 6) for c in v]


class AutoCADBackend:
    """Implementación sobre la API ActiveX de AutoCAD."""

    name = "autocad-com"

    def __init__(self) -> None:
        self._app = None
        self._progid = os.environ.get("AUTOCAD_PROGID", DEFAULT_PROGID)

    # ------------------------------------------------------------------ conexión
    @property
    def app(self):
        if self._app is None:
            try:
                self._app = win32com.client.GetActiveObject(self._progid)
            except pythoncom.com_error:
                # No hay AutoCAD abierto: lo lanzamos (puede tardar bastante).
                try:
                    self._app = win32com.client.Dispatch(self._progid)
                except pythoncom.com_error as exc:
                    raise RuntimeError(
                        f"No se pudo conectar ni iniciar AutoCAD (ProgID '{self._progid}'). "
                        "Comprueba que AutoCAD completo (no LT) está instalado y abierto."
                    ) from exc
                self._app.Visible = True
                for _ in range(120):
                    try:
                        if self._app.GetAcadState().IsQuiescent:
                            break
                    except pythoncom.com_error:
                        pass
                    time.sleep(1)
        return self._app

    @property
    def doc(self):
        app = self.app
        if app.Documents.Count == 0:
            app.Documents.Add()
        return app.ActiveDocument

    @property
    def ms(self):
        return self.doc.ModelSpace

    def _entity(self, handle: str):
        try:
            return self.doc.HandleToObject(handle)
        except pythoncom.com_error as exc:
            raise ValueError(f"No existe ninguna entidad con handle '{handle}'") from exc

    def _finish(self, ent, layer: str | None = None, color: int | None = None) -> dict:
        if layer:
            self._ensure_layer(layer)
            ent.Layer = layer
        if color is not None:
            ent.color = int(color)
        ent.Update()
        return self._describe(ent)

    def _ensure_layer(self, name: str):
        return self.doc.Layers.Add(name)  # Add devuelve la existente si ya está

    def _describe(self, ent) -> dict:
        info: dict[str, Any] = {
            "handle": ent.Handle,
            "type": ent.ObjectName,
            "layer": ent.Layer,
            "color": int(ent.color),
        }
        kind = ent.ObjectName
        try:
            if kind == "AcDbLine":
                info["start"] = _tuple(ent.StartPoint)
                info["end"] = _tuple(ent.EndPoint)
                info["length"] = round(ent.Length, 6)
            elif kind == "AcDbCircle":
                info["center"] = _tuple(ent.Center)
                info["radius"] = round(ent.Radius, 6)
            elif kind == "AcDbArc":
                info["center"] = _tuple(ent.Center)
                info["radius"] = round(ent.Radius, 6)
                info["start_angle_deg"] = round(math.degrees(ent.StartAngle), 6)
                info["end_angle_deg"] = round(math.degrees(ent.EndAngle), 6)
            elif kind == "AcDbPolyline":
                c = list(ent.Coordinates)
                info["points"] = [[round(c[i], 6), round(c[i + 1], 6)] for i in range(0, len(c), 2)]
                info["closed"] = bool(ent.Closed)
            elif kind in ("AcDbText", "AcDbMText"):
                info["text"] = ent.TextString
                info["insertion_point"] = _tuple(ent.InsertionPoint)
                info["height"] = round(ent.Height, 6)
            elif kind == "AcDbBlockReference":
                info["block_name"] = ent.EffectiveName
                info["insertion_point"] = _tuple(ent.InsertionPoint)
            elif kind == "AcDbEllipse":
                info["center"] = _tuple(ent.Center)
            elif kind == "AcDbPoint":
                info["position"] = _tuple(ent.Coordinates)
        except pythoncom.com_error:
            pass
        return info

    # ------------------------------------------------------------------ estado
    @_retry
    def status(self) -> dict:
        app = self.app
        docs = [app.Documents.Item(i).Name for i in range(app.Documents.Count)]
        return {
            "connected": True,
            "backend": self.name,
            "autocad_version": app.Version,
            "open_documents": docs,
            "active_document": (app.ActiveDocument.FullName or app.ActiveDocument.Name) if docs else None,
        }

    @_retry
    def drawing_info(self) -> dict:
        d = self.doc
        return {
            "name": d.Name,
            "path": d.FullName,
            "saved": bool(d.Saved),
            "active_layer": d.ActiveLayer.Name,
            "entity_count": d.ModelSpace.Count,
            "insunits": d.GetVariable("INSUNITS"),
            "extmin": _tuple(d.GetVariable("EXTMIN")),
            "extmax": _tuple(d.GetVariable("EXTMAX")),
        }

    # ------------------------------------------------------------------ documentos
    @_retry
    def new_drawing(self, template: str | None = None) -> dict:
        doc = self.app.Documents.Add(template) if template else self.app.Documents.Add()
        doc.Activate()
        return {"name": doc.Name}

    @_retry
    def open_drawing(self, path: str) -> dict:
        doc = self.app.Documents.Open(path)
        doc.Activate()
        return {"name": doc.Name, "path": doc.FullName}

    @_retry
    def save_drawing(self, path: str | None = None) -> dict:
        d = self.doc
        if path:
            d.SaveAs(path)
        else:
            d.Save()
        return {"saved": True, "path": d.FullName}

    # ------------------------------------------------------------------ dibujo
    @_retry
    def draw_line(self, start, end, layer=None, color=None) -> dict:
        return self._finish(self.ms.AddLine(_pt(start), _pt(end)), layer, color)

    @_retry
    def draw_polyline(self, points, closed=False, layer=None, color=None) -> dict:
        flat = [float(c) for p in points for c in p[:2]]
        pl = self.ms.AddLightWeightPolyline(_doubles(flat))
        pl.Closed = bool(closed)
        return self._finish(pl, layer, color)

    @_retry
    def draw_circle(self, center, radius, layer=None, color=None) -> dict:
        return self._finish(self.ms.AddCircle(_pt(center), float(radius)), layer, color)

    @_retry
    def draw_arc(self, center, radius, start_angle_deg, end_angle_deg, layer=None, color=None) -> dict:
        arc = self.ms.AddArc(
            _pt(center), float(radius), math.radians(start_angle_deg), math.radians(end_angle_deg)
        )
        return self._finish(arc, layer, color)

    @_retry
    def draw_ellipse(self, center, major_axis_end, ratio, layer=None, color=None) -> dict:
        el = self.ms.AddEllipse(_pt(center), _pt(major_axis_end), float(ratio))
        return self._finish(el, layer, color)

    @_retry
    def draw_point(self, position, layer=None, color=None) -> dict:
        return self._finish(self.ms.AddPoint(_pt(position)), layer, color)

    @_retry
    def add_text(self, text, position, height, rotation_deg=0.0, layer=None, color=None) -> dict:
        t = self.ms.AddText(text, _pt(position), float(height))
        t.Rotation = math.radians(rotation_deg)
        return self._finish(t, layer, color)

    @_retry
    def add_mtext(self, text, position, width, height, layer=None, color=None) -> dict:
        t = self.ms.AddMText(_pt(position), float(width), text)
        t.Height = float(height)
        return self._finish(t, layer, color)

    @_retry
    def add_aligned_dimension(self, p1, p2, text_position, layer=None, color=None) -> dict:
        dim = self.ms.AddDimAligned(_pt(p1), _pt(p2), _pt(text_position))
        return self._finish(dim, layer, color)

    @_retry
    def add_hatch(self, boundary_handles, pattern="SOLID", scale=1.0, layer=None, color=None) -> dict:
        boundary = [self._entity(h) for h in boundary_handles]
        # 0 = acHatchPatternTypePreDefined; True = asociativo
        hatch = self.ms.AddHatch(0, pattern, True)
        hatch.AppendOuterLoop(_objects(boundary))
        if pattern.upper() != "SOLID":
            hatch.PatternScale = float(scale)
        hatch.Evaluate()
        return self._finish(hatch, layer, color)

    @_retry
    def insert_block(self, name_or_path, position, scale=1.0, rotation_deg=0.0, layer=None) -> dict:
        s = float(scale)
        ref = self.ms.InsertBlock(_pt(position), name_or_path, s, s, s, math.radians(rotation_deg))
        return self._finish(ref, layer, None)

    # ------------------------------------------------------------------ capas
    @_retry
    def create_layer(self, name, color=None, linetype=None, make_current=False) -> dict:
        d = self.doc
        lay = self._ensure_layer(name)
        if color is not None:
            lay.color = int(color)
        if linetype:
            try:
                d.Linetypes.Item(linetype)
            except pythoncom.com_error:
                d.Linetypes.Load(linetype, "acad.lin")
            lay.Linetype = linetype
        if make_current:
            d.ActiveLayer = lay
        return {"name": lay.Name, "color": int(lay.color), "linetype": lay.Linetype}

    @_retry
    def set_current_layer(self, name) -> dict:
        d = self.doc
        d.ActiveLayer = d.Layers.Item(name)
        return {"active_layer": name}

    @_retry
    def list_layers(self) -> list[dict]:
        layers = self.doc.Layers
        out = []
        for i in range(layers.Count):
            lay = layers.Item(i)
            out.append(
                {
                    "name": lay.Name,
                    "color": int(lay.color),
                    "linetype": lay.Linetype,
                    "on": bool(lay.LayerOn),
                    "frozen": bool(lay.Freeze),
                    "locked": bool(lay.Lock),
                }
            )
        return out

    # ------------------------------------------------------------------ entidades
    @_retry
    def list_entities(self, layer=None, entity_type=None, limit=200) -> dict:
        ms = self.ms
        items, total = [], ms.Count
        for i in range(total):
            ent = ms.Item(i)
            if layer and ent.Layer.lower() != layer.lower():
                continue
            if entity_type and entity_type.lower() not in ent.ObjectName.lower():
                continue
            if len(items) >= limit:
                return {"entities": items, "truncated": True, "model_space_count": total}
            items.append(self._describe(ent))
        return {"entities": items, "truncated": False, "model_space_count": total}

    @_retry
    def get_entity(self, handle) -> dict:
        return self._describe(self._entity(handle))

    @_retry
    def delete_entities(self, handles) -> dict:
        for h in handles:
            self._entity(h).Delete()
        return {"deleted": list(handles)}

    @_retry
    def move_entities(self, handles, from_point, to_point) -> dict:
        for h in handles:
            self._entity(h).Move(_pt(from_point), _pt(to_point))
        return {"moved": list(handles)}

    @_retry
    def copy_entities(self, handles, from_point, to_point) -> dict:
        new = []
        for h in handles:
            c = self._entity(h).Copy()
            c.Move(_pt(from_point), _pt(to_point))
            new.append(c.Handle)
        return {"new_handles": new}

    @_retry
    def rotate_entities(self, handles, base_point, angle_deg) -> dict:
        for h in handles:
            self._entity(h).Rotate(_pt(base_point), math.radians(angle_deg))
        return {"rotated": list(handles)}

    @_retry
    def scale_entities(self, handles, base_point, factor) -> dict:
        for h in handles:
            self._entity(h).ScaleEntity(_pt(base_point), float(factor))
        return {"scaled": list(handles)}

    @_retry
    def mirror_entities(self, handles, p1, p2, delete_source=False) -> dict:
        new = []
        for h in handles:
            ent = self._entity(h)
            new.append(ent.Mirror(_pt(p1), _pt(p2)).Handle)
            if delete_source:
                ent.Delete()
        return {"new_handles": new}

    @_retry
    def offset_entity(self, handle, distance) -> dict:
        result = self._entity(handle).Offset(float(distance))
        # Los arrays de objetos llegan como PyIDispatch sin envolver.
        return {"new_handles": [win32com.client.Dispatch(o).Handle for o in result]}

    @_retry
    def set_entity_properties(self, handles, layer=None, color=None, linetype=None) -> dict:
        for h in handles:
            ent = self._entity(h)
            if layer:
                self._ensure_layer(layer)
                ent.Layer = layer
            if color is not None:
                ent.color = int(color)
            if linetype:
                ent.Linetype = linetype
            ent.Update()
        return {"updated": list(handles)}

    # ------------------------------------------------------------------ vista / sistema
    @_retry
    def zoom_extents(self) -> dict:
        self.app.ZoomExtents()
        return {"ok": True}

    @_retry
    def regen(self) -> dict:
        self.doc.Regen(1)  # acAllViewports
        return {"ok": True}

    @_retry
    def get_variable(self, name) -> dict:
        value = self.doc.GetVariable(name)
        if isinstance(value, tuple):
            value = list(value)
        return {"name": name.upper(), "value": value}

    @_retry
    def set_variable(self, name, value) -> dict:
        d = self.doc
        current = d.GetVariable(name)
        # SetVariable exige el mismo tipo que tiene la variable.
        if isinstance(current, int) and not isinstance(current, bool):
            value = int(value)
        elif isinstance(current, float):
            value = float(value)
        elif isinstance(current, tuple):
            value = _doubles(value)
        else:
            value = str(value)
        d.SetVariable(name, value)
        new = d.GetVariable(name)
        return {"name": name.upper(), "value": list(new) if isinstance(new, tuple) else new}

    @_retry
    def send_command(self, command: str) -> dict:
        if not command.endswith(("\n", " ")):
            command += "\n"
        self.doc.SendCommand(command)
        return {"sent": command}
