import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from babel.messages.mofile import write_mo
from babel.messages.pofile import read_po


def _compile_locales() -> None:
    """Compile committed .po catalogs to .mo so I18n can load them.

    .mo files are binary and git-ignored; tests regenerate them on demand.
    Runs at conftest import time - before any test module imports the
    example bot, whose I18n instance reads the .mo at construction.
    """
    locales_root = Path(__file__).resolve().parents[2] / "examples" / "pizza_locales"
    for po_path in locales_root.glob("*/LC_MESSAGES/messages.po"):
        mo_path = po_path.with_suffix(".mo")
        if mo_path.exists() and mo_path.stat().st_mtime >= po_path.stat().st_mtime:
            continue
        with po_path.open("rb") as po_file:
            catalog = read_po(po_file)
        with mo_path.open("wb") as mo_file:
            write_mo(mo_file, catalog)


_compile_locales()
