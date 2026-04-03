from __future__ import annotations

import os
import re
import threading
from typing import Callable, Optional, Sequence

from potato_stt.config import Settings

# Greedy int8 decode can be nondeterministic when BLAS/OpenMP uses multiple threads.
for _env_key, _env_val in (
    ("OMP_NUM_THREADS", "1"),
    ("MKL_NUM_THREADS", "1"),
    ("OPENBLAS_NUM_THREADS", "1"),
):
    os.environ.setdefault(_env_key, _env_val)

# Gemma 3 270M instruction-tuned, converted to CTranslate2 with int8 weights (see model card).
_DEFAULT_CT2_REPO = "jncraton/gemma-3-270m-it-ct2-int8"

# Display name -> English language name for prompts (clearer for the model than ISO codes alone).
TARGET_LANGUAGES: tuple[tuple[str, str], ...] = (
    ("en", "English"),
    ("es", "Spanish"),
    ("fr", "French"),
    ("de", "German"),
    ("it", "Italian"),
    ("pt", "Portuguese"),
    ("nl", "Dutch"),
    ("pl", "Polish"),
    ("ru", "Russian"),
    ("uk", "Ukrainian"),
    ("cs", "Czech"),
    ("sv", "Swedish"),
    ("da", "Danish"),
    ("no", "Norwegian"),
    ("fi", "Finnish"),
    ("el", "Greek"),
    ("tr", "Turkish"),
    ("ar", "Arabic"),
    ("he", "Hebrew"),
    ("hi", "Hindi"),
    ("bn", "Bengali"),
    ("ta", "Tamil"),
    ("te", "Telugu"),
    ("zh", "Chinese (Simplified)"),
    ("ja", "Japanese"),
    ("ko", "Korean"),
    ("vi", "Vietnamese"),
    ("th", "Thai"),
    ("id", "Indonesian"),
    ("ms", "Malay"),
    ("fil", "Filipino"),
)

_BOLD_TRANSLATION = re.compile(r"\*\*([^*]+?)\*\*", re.DOTALL)
_CYRILLIC_RE = re.compile(r"[\u0400-\u04FF]")
# Straight and fullwidth parentheses — model sometimes wraps the whole line.
_OUTER_PAREN_PAIRS: tuple[tuple[str, str], ...] = (
    ("(", ")"),
    ("（", "）"),
)

_lock = threading.Lock()
_generator = None  # type: ignore[assignment]
_tokenizer = None  # type: ignore[assignment]
_model_path: Optional[str] = None


class TranslationDependencyError(ImportError):
    """Raised when optional translation libraries are missing."""


def _unwrap_outer_parentheses(s: str) -> str:
    """Remove one or more layers of matching outer parentheses around the whole string."""
    t = s.strip()
    while len(t) >= 2:
        stripped = False
        for open_ch, close_ch in _OUTER_PAREN_PAIRS:
            if not (t.startswith(open_ch) and t.endswith(close_ch)):
                continue
            inner = t[len(open_ch) : -len(close_ch)].strip()
            if not inner:
                break
            # Reject "(a) (b)"-style strings: a closing paren followed later by "(" means
            # the outer pair is not wrapping a single phrase (char counts can still match).
            first_close = inner.find(close_ch)
            if first_close != -1 and inner.find(open_ch, first_close + 1) != -1:
                break
            t = inner
            stripped = True
            break
        if not stripped:
            break
    return t


# Opening/closing pairs (asymmetric) and symmetric pairs where open == close.
_OUTER_QUOTE_PAIRS: tuple[tuple[str, str], ...] = (
    ("\u201c", "\u201d"),  # “ ”
    ("\u2018", "\u2019"),  # ‘ ’
    ("\u00ab", "\u00bb"),  # « »
    ("\u201e", "\u201c"),  # „ “ (German)
    ("\u201e", "\u201d"),  # „ ”
    ("\u201a", "\u2018"),  # ‚ ‘
    ("\u300c", "\u300d"),  # 「 」
    ('"', '"'),
    ("'", "'"),
)


def _unwrap_outer_quotes(s: str) -> str:
    """Remove one or more layers of outer quotation marks (straight, curly, guillemets, etc.)."""
    t = s.strip()
    while len(t) >= 2:
        stripped = False
        for open_q, close_q in _OUTER_QUOTE_PAIRS:
            if not (t.startswith(open_q) and t.endswith(close_q)):
                continue
            inner = t[len(open_q) : -len(close_q)].strip()
            if not inner:
                break
            t = inner
            stripped = True
            break
        if not stripped:
            break
    return t


def _unwrap_quotes_when_period_after_close(s: str) -> str:
    """
    Handle ``“Hello”.`` (closing quote then sentence punctuation): model often places ``.`` outside the quote.
    """
    t = s.strip()
    while len(t) >= 1:
        stripped = False
        for open_q, close_q in _OUTER_QUOTE_PAIRS:
            if not t.startswith(open_q):
                continue
            body = t[len(open_q) :]
            end_rel = body.find(close_q)
            if end_rel < 0:
                continue
            inner = body[:end_rel].strip()
            after = body[end_rel + len(close_q) :].lstrip()
            if not inner:
                break
            if after:
                m = re.match(r"^([.!?…]+)(\s*)$", after)
                if m is None:
                    break
                suffix = m.group(1) + m.group(2)
                t = (inner + suffix.rstrip()).strip()
            else:
                t = inner
            stripped = True
            break
        if not stripped:
            break
    return t


def _collapse_internal_spaces(s: str) -> str:
    """Collapse runs of spaces; keep newlines between lines (subtitle / paragraph breaks)."""
    if not s:
        return s
    lines = s.split("\n")
    out = [re.sub(r" +", " ", ln.strip()) for ln in lines]
    return "\n".join(ln for ln in out if ln).strip()


def finalize_translation_output(s: str) -> str:
    """
    Last-step cleanup after model decode: outer parentheses, quotation marks (many styles),
    optional ``.”``-style punctuation after the closing quote, and duplicate spaces.

    Call this on the final string shown to the user (paste / transcript / subtitles).
    """
    t = _unwrap_outer_parentheses(s)
    t = _unwrap_outer_quotes(t)
    t = _unwrap_quotes_when_period_after_close(t)
    t = _unwrap_outer_quotes(t)
    t = _collapse_internal_spaces(t)
    return t


def language_display_for_code(code: str) -> str:
    c = (code or "").strip().lower()
    for k, label in TARGET_LANGUAGES:
        if k == c:
            return label
    return "English"


def _prompt_language_tag(display_name: str) -> str:
    """ISO-style tag for prompts (e.g. en, fr). Avoids spelling full language names in the prompt."""
    d = (display_name or "").strip().casefold()
    for code, label in TARGET_LANGUAGES:
        if label.casefold() == d:
            return code
    return "en"


# Model sometimes answers *about* the instructions instead of translating (small IT models).
_BAD_MODEL_META_MARKERS: tuple[str, ...] = (
    "the provided text",
    "it does not contain",
    "does not contain any quotation",
    "does not include a title",
    "simple sentence",
    "no leading or trailing quotes",
    "as an ai language model",
    "i cannot translate",
    "i can't translate",
    "please provide me with",
    "please provide the text",
    "please tell me",
    "what you want me to do",
    "check for translation",
    "goal of the translation",
    "what is the goal",
    "the more details",
    "better i can assist",
    "i can assist you",
    "i am not able to",
    "i'm not able to",
    "i'm ready",
    "i am ready",
    "how can i assist",
    "how can i help",
    "i will provide",
    "i will do my best",
    "accurate and helpful",
    "helpful and accurate response",
    "helpful translations",
    "helpful response based on your request",
)


def _looks_like_meta_or_refusal(s: str) -> bool:
    low = (s or "").strip().casefold()
    if not low:
        return True
    if len(low) > 900:
        return True
    return any(m in low for m in _BAD_MODEL_META_MARKERS)


def _english_target_but_cyrillic_output(cleaned: str, chunk: str, lang_tag: str) -> bool:
    """Target is English but model kept Cyrillic (common failure mode for RU→EN)."""
    if lang_tag != "en":
        return False
    if not _CYRILLIC_RE.search(chunk):
        return False
    return bool(_CYRILLIC_RE.search(cleaned))


def _translation_too_shallow_vs_source(cleaned: str, chunk: str) -> bool:
    """Labels like ``Translation:`` or a single word while the source is a full sentence."""
    c = (cleaned or "").strip()
    s = (chunk or "").strip()
    if not c or not s:
        return True
    if c.casefold() == s.casefold():
        return False
    src_w = len(re.findall(r"\w+", s, flags=re.UNICODE))
    out_w = len(re.findall(r"\w+", c, flags=re.UNICODE))
    if src_w >= 5 and out_w <= 1 and len(c) < 32:
        return True
    if src_w >= 8 and len(c) < 12:
        return True
    return False


def _translation_output_is_bad(cleaned: str, chunk: str, lang_tag: str) -> bool:
    if not cleaned.strip():
        return True
    if cleaned.casefold() == chunk.casefold():
        return True
    if _translation_too_shallow_vs_source(cleaned, chunk):
        return True
    if _looks_like_meta_or_refusal(cleaned):
        return True
    if _english_target_but_cyrillic_output(cleaned, chunk, lang_tag):
        return True
    return False


def _strip_translation_artifacts(raw: str, source: str) -> str:
    """Turn model output into plain translated text (270M IT often wraps answers in **bold**)."""
    t = (raw or "").strip()
    if not t:
        return t
    m = _BOLD_TRANSLATION.search(t)
    if m:
        inner = m.group(1).strip()
        if inner:
            return finalize_translation_output(inner)
    lines = [ln.strip() for ln in t.splitlines() if ln.strip()]
    src = (source or "").strip()
    if src:
        lines = [ln for ln in lines if ln.casefold() != src.casefold()]
    if not lines:
        return finalize_translation_output(t)
    # Prefer the last non-empty line (often the actual translation after a preamble).
    return finalize_translation_output(lines[-1].strip())


def _chunk_text(text: str, *, max_chars: int) -> list[str]:
    t = text.strip()
    if not t:
        return []
    if len(t) <= max_chars:
        return [t]
    parts: list[str] = []
    buf: list[str] = []
    n = 0
    for para in t.split("\n\n"):
        p = para.strip()
        if not p:
            continue
        if n + len(p) + 2 > max_chars and buf:
            parts.append("\n\n".join(buf))
            buf = []
            n = 0
        if len(p) > max_chars:
            if buf:
                parts.append("\n\n".join(buf))
                buf = []
                n = 0
            start = 0
            while start < len(p):
                parts.append(p[start : start + max_chars].strip())
                start += max_chars
            continue
        buf.append(p)
        n += len(p) + 2
    if buf:
        parts.append("\n\n".join(buf))
    return [x for x in parts if x.strip()]


def _ensure_loaded(
    settings: Settings,
    *,
    on_status: Optional[Callable[[str], None]] = None,
) -> None:
    global _generator, _tokenizer, _model_path
    with _lock:
        if _generator is not None and _tokenizer is not None:
            return
        try:
            import ctranslate2
            from huggingface_hub import snapshot_download
            from transformers import AutoTokenizer
        except ImportError as e:
            raise TranslationDependencyError(
                "Translation requires optional packages. Install repo requirements.txt "
                "(ctranslate2, transformers, sentencepiece, jinja2, huggingface_hub)."
            ) from e

        repo = (settings.translate_ct2_repo or _DEFAULT_CT2_REPO).strip()
        if on_status is not None:
            on_status(
                "Downloading Gemma 3 270M translation model (int8 CTranslate2, first run only)…"
            )
        path = snapshot_download(repo_id=repo)
        _model_path = path
        # Explicit False: avoids Transformers' Mistral-regex warning for local Gemma tokenizers
        # (the repo is Gemma, not Mistral). Do not use True here — it assumes `backend_tokenizer`
        # on the Rust `Tokenizer` and can raise AttributeError.
        _tokenizer = AutoTokenizer.from_pretrained(
            path,
            trust_remote_code=True,
            fix_mistral_regex=False,
        )
        device = (settings.translate_device or "cpu").strip().lower()
        if device == "auto":
            device = "cuda" if _cuda_available() else "cpu"
        compute = (settings.translate_compute_type or "int8_float32").strip().lower()
        # Single-thread decode + thread env above reduces flaky greedy outputs on Windows.
        _generator = ctranslate2.Generator(
            path,
            device=device,
            compute_type=compute,
            intra_threads=1,
            inter_threads=1,
        )


def _cuda_available() -> bool:
    try:
        from ctranslate2 import get_cuda_device_count

        return int(get_cuda_device_count()) > 0
    except Exception:
        return False


def translate_text(
    text: str,
    *,
    target_language: str,
    settings: Optional[Settings] = None,
    on_status: Optional[Callable[[str], None]] = None,
    max_input_chars_per_chunk: int = 1200,
    max_new_tokens: int = 384,
) -> str:
    """
    Translate ASR text into ``target_language`` (display name, e.g. 'French').

    Uses Gemma 3 270M IT in CTranslate2 int8 weights (``int8_float32`` compute by default).
    """
    cfg = settings if settings is not None else Settings()
    t = (text or "").strip()
    if not t:
        return ""
    lang = (target_language or "").strip()
    if not lang:
        return t

    _ensure_loaded(cfg, on_status=on_status)
    assert _generator is not None and _tokenizer is not None

    chunks = _chunk_text(t, max_chars=max_input_chars_per_chunk)
    out_parts: list[str] = []
    for i, chunk in enumerate(chunks):
        if on_status is not None and len(chunks) > 1:
            on_status(f"Translating ({i + 1}/{len(chunks)})…")
        out_parts.append(
            _translate_one_chunk(
                chunk,
                target_language=lang,
                max_new_tokens=max_new_tokens,
            )
        )
    return "\n\n".join(out_parts).strip()


# CTranslate2 ``max_length`` counts total decoder length including prefilled prompt tokens when
# ``include_prompt_in_result=False``. Passing only ``max_new_tokens`` caps below prompt length for
# long inputs (e.g. ~1k Cyrillic subword tokens), producing garbage and apparent 'no translation'.
_CT2_DECODE_ABS_MAX = 32768


def _ct2_decode_max_length(num_prompt_tokens: int, max_new_tokens: int) -> int:
    npt = max(0, int(num_prompt_tokens))
    mnt = max(1, int(max_new_tokens))
    return min(npt + mnt, _CT2_DECODE_ABS_MAX)


def _translate_one_chunk(
    chunk: str,
    *,
    target_language: str,
    max_new_tokens: int,
) -> str:
    """Translate a single chunk. Returns *chunk* unchanged when the model fails."""
    assert _generator is not None and _tokenizer is not None
    tag = _prompt_language_tag(target_language)
    messages = [
        {
            "role": "user",
            "content": f"Translate this text to {target_language}:\n{chunk}",
        }
    ]

    def _decode(
        msgs: list[dict],
        *,
        repetition_penalty: float = 1.05,
        sampling_temperature: Optional[float] = None,
    ) -> str:
        ids = _tokenizer.apply_chat_template(
            msgs,
            add_generation_prompt=True,
            tokenize=True,
            return_dict=False,
        )
        tokens = _tokenizer.convert_ids_to_tokens(ids)
        gen_kwargs: dict = dict(
            max_length=_ct2_decode_max_length(len(tokens), max_new_tokens),
            include_prompt_in_result=False,
            repetition_penalty=repetition_penalty,
        )
        if sampling_temperature is not None:
            gen_kwargs.update(
                sampling_topk=50,
                sampling_temperature=sampling_temperature,
                sampling_topp=0.92,
            )
        else:
            gen_kwargs["sampling_topk"] = 1
        result = _generator.generate_batch([tokens], **gen_kwargs)
        raw = _tokenizer.convert_tokens_to_string(result[0].sequences[0])
        return finalize_translation_output(
            _strip_translation_artifacts(raw, chunk).strip()
        )

    with _lock:
        greedy = _decode(messages)
        if not _translation_output_is_bad(greedy, chunk, tag):
            return greedy
        sampled = _decode(
            messages, sampling_temperature=0.3, repetition_penalty=1.1
        )
        if not _translation_output_is_bad(sampled, chunk, tag):
            return sampled

    return chunk


def translate_cue_texts(
    texts: Sequence[str],
    *,
    target_language: str,
    settings: Optional[Settings] = None,
    on_status: Optional[Callable[[str], None]] = None,
) -> list[str]:
    """Translate subtitle cue strings, preserving order (one generation per non-empty cue)."""
    cfg = settings if settings is not None else Settings()
    _ensure_loaded(cfg, on_status=on_status)
    out: list[str] = []
    n = len(texts)
    for i, raw in enumerate(texts):
        s = (raw or "").strip()
        if not s:
            out.append("")
            continue
        if on_status is not None and n > 3:
            on_status(f"Translating subtitles ({i + 1}/{n})…")
        out.append(
            translate_text(
                s,
                target_language=target_language,
                settings=cfg,
                on_status=None,
                max_input_chars_per_chunk=2000,
                max_new_tokens=256,
            )
        )
    return out
