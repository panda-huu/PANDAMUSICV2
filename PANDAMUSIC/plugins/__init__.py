import glob, importlib

from ..console import logs
from os.path import basename, dirname, isfile


def __list_all_plugins():
    plugin_paths = glob.glob(dirname(__file__) + "/*.py")
    
    all_plugins = [
        basename(f)[:-3]
        for f in plugin_paths
        if isfile(f) and f.endswith(".py")
        and not f.endswith("__init__.py")
    ]

    return all_plugins


ALL_PLUGINS = sorted(__list_all_plugins())
__all__ = ALL_PLUGINS + ["ALL_PLUGINS"]


async def import_all_plugins():
    for all_plugin in ALL_PLUGINS:
        try:
            imported_plugin = importlib.import_module(
                "PANDAMUSIC.plugins." + all_plugin
            )
        except Exception as e:
            logs(__name__).error(
                f"❌ Failed to import: {all_plugin}\n↪️ Reason: {e}"
            )
            continue
