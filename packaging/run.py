"""Entry point used by PyInstaller (absolute imports, so the package resolves)."""

from ets2_triple_monitor.gui import main

if __name__ == "__main__":
    raise SystemExit(main())
