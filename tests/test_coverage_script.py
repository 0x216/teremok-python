import importlib.util
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "gen_coverage.py"


def load_script():
    spec = importlib.util.spec_from_file_location("gen_coverage", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules["gen_coverage"] = module
    spec.loader.exec_module(module)
    return module


def test_render_contains_every_tier_and_no_unknowns() -> None:
    gen = load_script()
    text = gen.render()
    assert "| `SendMessage` |" in text and "✅" in text
    assert "| `DeleteMessage` |" in text and "🟡" in text
    assert "| `GetUpdates` |" in text and "📋" in text
    # every table row got a real status - no KeyError fallbacks
    assert "UNKNOWN" not in text


def test_render_covers_all_aiogram_methods() -> None:
    import aiogram.methods as methods_module
    from aiogram.methods import TelegramMethod

    gen = load_script()
    text = gen.render()
    method_classes = [
        getattr(methods_module, name)
        for name in methods_module.__all__
        if isinstance(getattr(methods_module, name), type)
        and issubclass(getattr(methods_module, name), TelegramMethod)
        and getattr(methods_module, name) is not TelegramMethod
    ]
    assert len(method_classes) > 100  # sanity: aiogram ships 100+ methods
    for cls in method_classes:
        assert f"| `{cls.__name__}` |" in text


def test_render_covers_every_update_type() -> None:
    from aiogram.types import Update

    gen = load_script()
    text = gen.render()
    assert "| `message` |" in text
    assert "| `inline_query` |" in text
    assert "| `edited_message` |" in text
    update_fields = [name for name in Update.model_fields if name != "update_id"]
    assert len(update_fields) > 15  # sanity: Telegram ships 15+ update types
    for name in update_fields:
        assert f"| `{name}` |" in text
