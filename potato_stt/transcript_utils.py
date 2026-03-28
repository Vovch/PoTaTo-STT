from __future__ import annotations

import re

# ONNX ASR / SentencePiece often maps out-of-vocabulary Cyrillic "ё" to <unk>.
_UNK_TOKEN = re.compile(r"<unk>", re.IGNORECASE)


def repair_asr_unk_tokens(text: str) -> str:
    """
    Replace tokenizer <unk> placeholders with "ё" when the line contains Cyrillic.
    The Parakeet vocabulary commonly omits ё, so the model emits <unk> instead.
    """
    if not text or not re.search(r"[а-яёА-ЯЁ]", text):
        return text
    return _UNK_TOKEN.sub("ё", text)


def finalize_sentence_for_clipboard(text: str) -> str:
    """
    Trim outer whitespace, then ensure a space after final . ! ? so paste does not
    drop that space (plain strip() would remove it).
    """
    t = text.strip()
    if not t:
        return t
    if t[-1] in ".!?":
        return t + " "
    return t


def normalize_phrase_spacing(text: str) -> str:
    """
    Insert spaces between phrases when the model omits them after punctuation
    (e.g. 'Hello.How are you' -> 'Hello. How are you').

    Also ends the string with a space when it ends in . ! ? so after paste the
    caret can continue typing without the next word sticking to the period.
    """
    t = repair_asr_unk_tokens(text)
    t = t.strip()
    if not t:
        return t

    # . ! ? immediately before an opening quote (e.g. He said."Yes" -> ... said. "Yes")
    t = re.sub(r'([.!?])(["\'\u201c\u2018])', r"\1 \2", t)

    def _after_sentence_end(m: re.Match[str]) -> str:
        punct, nxt = m.group(1), m.group(2)
        if nxt.isalpha():
            return f"{punct} {nxt}"
        return m.group(0)

    # . ! ? followed immediately by a letter
    t = re.sub(r"([.!?])([^\s.!?])", _after_sentence_end, t)

    def _after_comma_semi(m: re.Match[str]) -> str:
        punct, nxt = m.group(1), m.group(2)
        if nxt.isalpha():
            return f"{punct} {nxt}"
        return m.group(0)

    # , ; before a word (avoid touching decimals like 1,234)
    t = re.sub(r"([,;])([^\s,;])", _after_comma_semi, t)

    t = re.sub(r" +", " ", t)
    return finalize_sentence_for_clipboard(t)
