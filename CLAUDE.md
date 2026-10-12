# Guía para Claude: control de AutoCAD

Este proyecto contiene un servidor MCP (`autocad`) que controla AutoCAD por COM.
Cuando el usuario pida dibujar o modificar algo en AutoCAD, usa las herramientas
`mcp__autocad__*`.

## Flujo de trabajo

1. Empieza con `autocad_status` y `drawing_info` para conocer el dibujo activo,
   sus unidades (`INSUNITS`: 4 = mm, 5 = cm, 6 = m, 1 = pulgadas) y lo que ya hay.
2. Si el usuario no indica unidades, pregunta o asume las del dibujo y dilo.
3. Organiza el dibujo en capas con nombres claros (`Muros`, `Ejes`, `Cotas`,
   `Textos`, `Mobiliario`...) creadas con `create_layer` (color y tipo de línea).
4. Para más de ~5 entidades usa `execute_batch`: una sola llamada es mucho más
   rápida que muchas llamadas sueltas.
5. Al terminar, `zoom_extents` y resume qué se creó (capas, nº de entidades).
6. Guarda solo si el usuario lo pide (`save_drawing`).

## Convenciones

- Puntos `[x, y]` o `[x, y, z]`; ángulos en grados, antihorario desde +X.
- Colores ACI: 1 rojo, 2 amarillo, 3 verde, 4 cian, 5 azul, 6 magenta,
  7 blanco/negro, 8 gris, 256 PorCapa. Preferir color PorCapa y asignar el color a la capa.
- Guarda los `handle` que devuelven las herramientas para editar después
  (mover, copiar, sombrear, borrar). Si no los tienes, usa `list_entities`.
- `send_command` es el último recurso (comandos sin herramienta propia, como
  `FILLET`, `TRIM`, `ARRAY`, `PLOT`, o AutoLISP). Usa la forma de línea de
  comandos (`-LAYER`, `-PLOT`, `_.` para nombres internacionales) para evitar
  cuadros de diálogo. Es asíncrono: verifica el resultado con `list_entities`.
- Antes de borrar muchas entidades o sobrescribir un archivo, confirma con el usuario.

## Desarrollo

- Código en `src/autocad_mcp/`: `server.py` (herramientas MCP), `com_backend.py`
  (AutoCAD real), `mock_backend.py` (simulado), `worker.py` (hilo COM único).
- Pruebas sin AutoCAD: `AUTOCAD_MCP_MOCK=1 pytest`.
- Al añadir una herramienta: método en ambos backends + función en `server.py`
  (+ añadirla a `BATCH_OPERATIONS` si es de dibujo/edición) + prueba en `tests/`.
