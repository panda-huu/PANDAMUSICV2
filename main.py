import os
import sys
import runpy
os.system("pip install -U kurigram")
# Root directory set karo
ROOT = os.path.dirname(os.path.abspath(__file__))
os.chdir(ROOT)

if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# PANDAMUSIC package start
if __name__ == "__main__":
    try:
        runpy.run_module("PANDAMUSIC", run_name="__main__", alter_sys=True)
    except KeyboardInterrupt:
        print("\nBot stopped by user.")
    except Exception as e:
        print(f"Failed to start bot: {e}")
        sys.exit(1)
