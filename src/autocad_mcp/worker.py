"""Ejecuta todas las llamadas al backend en un único hilo dedicado.

COM exige que los objetos se usen desde el hilo (apartamento) que los creó,
pero el SDK de MCP puede ejecutar herramientas en hilos distintos. Este
worker serializa todas las llamadas en un solo hilo con COM inicializado.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable

CALL_TIMEOUT_S = 300


def _com_init() -> None:
    try:
        import pythoncom
    except ImportError:  # backend simulado / no Windows
        return
    pythoncom.CoInitialize()


class Worker:
    def __init__(self) -> None:
        self._pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="autocad-com", initializer=_com_init)

    def call(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        return self._pool.submit(fn, *args, **kwargs).result(timeout=CALL_TIMEOUT_S)
