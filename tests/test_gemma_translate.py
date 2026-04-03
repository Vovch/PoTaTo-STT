import unittest
from unittest.mock import MagicMock, patch

from potato_stt import gemma_translate
from potato_stt.gemma_translate import (
    _ct2_decode_max_length,
    _looks_like_meta_or_refusal,
    _prompt_language_tag,
    _translation_output_is_bad,
    _strip_translation_artifacts,
    finalize_translation_output,
    language_display_for_code,
)


class TestFinalizeTranslationOutput(unittest.TestCase):
    def test_strips_outer_parentheses(self) -> None:
        self.assertEqual(finalize_translation_output("(Hello world.)"), "Hello world.")
        self.assertEqual(finalize_translation_output("((Nested))"), "Nested")

    def test_keeps_inner_parentheses_when_unbalanced(self) -> None:
        self.assertEqual(finalize_translation_output("(a) (b)"), "(a) (b)")

    def test_collapses_spaces(self) -> None:
        self.assertEqual(finalize_translation_output("  a   b  "), "a b")

    def test_strips_curly_double_quotes(self) -> None:
        self.assertEqual(finalize_translation_output("\u201cHello.\u201d"), "Hello.")
        # Period after the closing quote (common model pattern)
        self.assertEqual(finalize_translation_output("\u201cHello\u201d."), "Hello.")

    def test_strips_double_layer_straight_quotes(self) -> None:
        self.assertEqual(finalize_translation_output('""Hi there""'), "Hi there")

    def test_strips_guillemets(self) -> None:
        self.assertEqual(finalize_translation_output("\u00abBonjour\u00bb"), "Bonjour")


class TestPromptAndMetaDetection(unittest.TestCase):
    def test_prompt_language_tag(self) -> None:
        self.assertEqual(_prompt_language_tag("English"), "en")
        self.assertEqual(_prompt_language_tag("French"), "fr")

    def test_meta_refusal_heuristic(self) -> None:
        bad = (
            "The provided text is a simple sentence. It does not contain any quotation marks, "
            "no leading or trailing quotes."
        )
        self.assertTrue(_looks_like_meta_or_refusal(bad))
        self.assertFalse(_looks_like_meta_or_refusal("Hello world."))
        self.assertFalse(_looks_like_meta_or_refusal("Проверка связи."))

    def test_cyrillic_output_bad_for_english_target(self) -> None:
        chunk = "Проверка перевода"
        self.assertTrue(
            _translation_output_is_bad("Что вы хотите?", chunk, "en"),
        )
        self.assertFalse(
            _translation_output_is_bad("Verification check.", chunk, "en"),
        )

    def test_label_only_output_bad_for_long_source(self) -> None:
        chunk = "Проверка перевода на английский язык"
        self.assertTrue(_translation_output_is_bad("Translation:", chunk, "en"))
        self.assertFalse(
            _translation_output_is_bad("Verification of translation to English.", chunk, "en"),
        )


class TestCt2DecodeLength(unittest.TestCase):
    def test_max_length_includes_prompt_tokens(self) -> None:
        """CTranslate2 max_length is prompt + new tokens, not new tokens alone."""
        self.assertEqual(_ct2_decode_max_length(1000, 384), 1384)
        self.assertEqual(_ct2_decode_max_length(0, 256), 256)


class TestGemmaTranslateHelpers(unittest.TestCase):
    def test_language_display_for_code(self) -> None:
        self.assertEqual(language_display_for_code("fr"), "French")
        self.assertEqual(language_display_for_code("FR"), "French")
        self.assertEqual(language_display_for_code("xx"), "English")

    def test_strip_bold_translation(self) -> None:
        raw = 'The translation is:\n\n**Le chat dort sur le canapé.**\n'
        out = _strip_translation_artifacts(raw, "The cat sleeps on the sofa.")
        self.assertEqual(out, "Le chat dort sur le canapé.")

    def test_strip_drops_source_lines(self) -> None:
        raw = "The cat sleeps on the sofa.\nLe chat dort."
        out = _strip_translation_artifacts(raw, "The cat sleeps on the sofa.")
        self.assertEqual(out, "Le chat dort.")

    def test_translate_text_passes_max_new_tokens_to_chunk(self) -> None:
        """Regression: _translate_one_chunk must receive max_new_tokens (no stray NameError)."""
        prev_gen, prev_tok = gemma_translate._generator, gemma_translate._tokenizer
        try:
            gemma_translate._generator = MagicMock()
            gemma_translate._tokenizer = MagicMock()
            with patch.object(gemma_translate, "_ensure_loaded"), patch.object(
                gemma_translate,
                "_translate_one_chunk",
                return_value="translated",
            ) as m:
                out = gemma_translate.translate_text(
                    "hello",
                    target_language="German",
                    max_new_tokens=123,
                )
            self.assertEqual(out, "translated")
            self.assertEqual(m.call_args.kwargs["max_new_tokens"], 123)
        finally:
            gemma_translate._generator = prev_gen
            gemma_translate._tokenizer = prev_tok


if __name__ == "__main__":
    unittest.main()
