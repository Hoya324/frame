import sys
import types
from unittest.mock import MagicMock

from crawler.enrich.translator import TARGET_LOCALES, detect_lang, targets_for


def test_detect_lang_hangul():
    assert detect_lang("을지로의 밤") == "ko"


def test_detect_lang_kana_or_han():
    assert detect_lang("カリフォルニア") == "ja"
    assert detect_lang("世田谷") == "ja"  # 한자만 있어도 일본어로 본다 (한국어는 한글 사용)


def test_detect_lang_latin_fallback():
    assert detect_lang("BOOK AND SONS") == "en"


def test_targets_excludes_source():
    assert set(targets_for("ko")) == {"en", "ja"}
    assert set(targets_for("ja")) == {"en", "ko"}
    assert set(TARGET_LOCALES) == {"ko", "en", "ja"}


def _install_fake_argos(monkeypatch):
    pkg = types.ModuleType("argostranslate.package")
    trans = types.ModuleType("argostranslate.translate")
    pkg.get_installed_packages = MagicMock(return_value=[])
    pkg.get_available_packages = MagicMock(return_value=[])
    pkg.update_package_index = MagicMock()
    trans.translate = MagicMock(side_effect=lambda text, frm, to: f"[{to}]{text}")
    root = types.ModuleType("argostranslate")
    monkeypatch.setitem(sys.modules, "argostranslate", root)
    monkeypatch.setitem(sys.modules, "argostranslate.package", pkg)
    monkeypatch.setitem(sys.modules, "argostranslate.translate", trans)
    return pkg, trans


def test_argos_translator_delegates(monkeypatch):
    from crawler.enrich.translator import ArgosTranslator

    _pkg, trans = _install_fake_argos(monkeypatch)
    t = ArgosTranslator()
    assert t.translate("hello", "en", "ko") == "[ko]hello"
    trans.translate.assert_called_once_with("hello", "en", "ko")


def test_argos_translator_blank_passthrough(monkeypatch):
    from crawler.enrich.translator import ArgosTranslator

    _install_fake_argos(monkeypatch)
    t = ArgosTranslator()
    assert t.translate("   ", "en", "ko") == "   "
