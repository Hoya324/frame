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


def test_pivots_ko_to_ja_through_english(monkeypatch):
    # Argos has no direct KO<->JA package and does not auto-pivot, so a non-English
    # pair must be routed from->en then en->to. Earlier this raised AttributeError
    # in CI and dropped every Japanese translation of Korean content.
    from crawler.enrich.translator import ArgosTranslator

    _pkg, trans = _install_fake_argos(monkeypatch)
    t = ArgosTranslator()
    assert t.translate("제목", "ko", "ja") == "[ja][en]제목"
    assert trans.translate.call_args_list == [
        (("제목", "ko", "en"),),
        (("[en]제목", "en", "ja"),),
    ]


def test_ensure_installs_both_pivot_legs(monkeypatch):
    from crawler.enrich.translator import ArgosTranslator

    pkg, _trans = _install_fake_argos(monkeypatch)
    ko_en = MagicMock(from_code="ko", to_code="en")
    en_ja = MagicMock(from_code="en", to_code="ja")
    pkg.get_available_packages = MagicMock(return_value=[ko_en, en_ja])
    t = ArgosTranslator()
    t.translate("제목", "ko", "ja")
    ko_en.install.assert_called_once()
    en_ja.install.assert_called_once()
