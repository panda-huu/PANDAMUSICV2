import glob
import importlib
import sys

from ..console import logs
from os.path import basename, dirname, isfile

_PLUGINS_LOADED = False


def __list_all_plugins():
    plugin_paths = glob.glob(dirname(__file__) + "/*.py")

    all_plugins = [
        basename(f)[:-3]
        for f in plugin_paths
        if isfile(f)
        and f.endswith(".py")
        and not f.endswith("__init__.py")
    ]

    return all_plugins


ALL_PLUGINS = sorted(__list_all_plugins())
__all__ = ALL_PLUGINS + ["ALL_PLUGINS"]


async def import_all_plugins():
    """Import each plugin once. Prevents double handler registration."""
    global _PLUGINS_LOADED

    if _PLUGINS_LOADED:
        logs(__name__).warning(
            "⚠️ Plugins already loaded — skipping re-import (prevents double replies)"
        )
        return

    for all_plugin in ALL_PLUGINS:
        module_name = "PANDAMUSIC.plugins." + all_plugin

        # Already in sys.modules = already imported somewhere
        if module_name in sys.modules:
            logs(__name__).info(f"↪️ Skip (already loaded): {all_plugin}")
            continue

        try:
            importlib.import_module(module_name)
            logs(__name__).info(f"✅ Loaded plugin: {all_plugin}")
        except Exception as e:
            logs(__name__).error(
                f"❌ Failed to import: {all_plugin}\n↪️ Reason: {e}"
            )
            continue

    _PLUGINS_LOADED = True
    logs(__name__).info(f"✅ All plugins loaded ({len(ALL_PLUGINS)} files)")
