"""Push-to-talk: canonical specs, matching, labels, and settings load/save."""
from __future__ import annotations

import json
from typing import Optional

from PySide6.QtCore import QSettings
from pynput import keyboard, mouse

# Legacy single-key setting (migrated to PTT_KEYS_SETTING)
PTT_KEY_SETTING = "push_to_talk_key"
PTT_KEYS_SETTING = "push_to_talk_keys"

PTT_KEY_DEFAULT = "right_ctrl"
DEFAULT_PTT_SPECS: list[str] = [PTT_KEY_DEFAULT]

_PRESET_CHOICES: list[tuple[str, str]] = [
    ("right_ctrl", "Right Ctrl"),
    ("left_ctrl", "Left Ctrl"),
    ("right_alt", "Right Alt"),
    ("left_alt", "Left Alt"),
    ("space", "Space"),
    ("mouse_x1", "Mouse button 4 (side / back)"),
    ("mouse_x2", "Mouse button 5 (side / forward)"),
    ("mouse_middle", "Middle mouse button"),
]
_PRESET_IDS = frozenset(p[0] for p in _PRESET_CHOICES)
_PRESET_LABELS = dict(_PRESET_CHOICES)


def ptt_key_choices() -> list[tuple[str, str]]:
    return list(_PRESET_CHOICES)


def normalize_spec(spec: str) -> str:
    """Canonical form: preset id, vk:NNN, or mouse:x1|x2|middle|left|right."""
    s = str(spec).strip()
    if not s:
        return PTT_KEY_DEFAULT
    if s.startswith("mouse:"):
        tail = s.split(":", 1)[1].lower()
        return f"mouse:{tail}"
    # Legacy mouse_* preset ids
    if s.startswith("mouse_"):
        tail = s.replace("mouse_", "", 1).lower()
        return f"mouse:{tail}"
    if s.startswith("vk:"):
        try:
            n = int(s.split(":", 1)[1].strip(), 0)
            return f"vk:{n}"
        except ValueError:
            return PTT_KEY_DEFAULT
    if s in _PRESET_IDS:
        return s
    return PTT_KEY_DEFAULT


def normalize_spec_list(raw: Optional[list]) -> list[str]:
    if not raw:
        return list(DEFAULT_PTT_SPECS)
    out: list[str] = []
    seen: set[str] = set()
    for item in raw:
        if not isinstance(item, str):
            continue
        n = normalize_spec(item)
        if n not in seen:
            seen.add(n)
            out.append(n)
    return out if out else list(DEFAULT_PTT_SPECS)


def load_ptt_specs(qsettings: QSettings) -> list[str]:
    raw_json = qsettings.value(PTT_KEYS_SETTING, None)
    if isinstance(raw_json, str) and raw_json.strip():
        try:
            data = json.loads(raw_json)
            if isinstance(data, list):
                return normalize_spec_list(data)
        except json.JSONDecodeError:
            pass
    # Migrate legacy single value
    legacy = qsettings.value(PTT_KEY_SETTING, None)
    if isinstance(legacy, str) and legacy.strip():
        return normalize_spec_list([legacy])
    return list(DEFAULT_PTT_SPECS)


def save_ptt_specs(qsettings: QSettings, specs: list[str]) -> None:
    norm = normalize_spec_list(specs)
    qsettings.setValue(PTT_KEYS_SETTING, json.dumps(norm))
    # Clear legacy so new code path is authoritative
    qsettings.remove(PTT_KEY_SETTING)


def mouse_button_to_spec(btn: mouse.Button) -> Optional[str]:
    if btn == mouse.Button.x1:
        return "mouse:x1"
    if btn == mouse.Button.x2:
        return "mouse:x2"
    if btn == mouse.Button.middle:
        return "mouse:middle"
    if btn == mouse.Button.left:
        return "mouse:left"
    if btn == mouse.Button.right:
        return "mouse:right"
    return None


def mouse_spec_to_button(spec: str) -> Optional[mouse.Button]:
    ns = normalize_spec(spec)
    if not ns.startswith("mouse:"):
        return None
    tail = ns.split(":", 1)[1]
    m = {
        "x1": mouse.Button.x1,
        "x2": mouse.Button.x2,
        "middle": mouse.Button.middle,
        "left": mouse.Button.left,
        "right": mouse.Button.right,
    }
    return m.get(tail)


def keyboard_matches_preset(preset_id: str, key) -> bool:  # type: ignore[no-untyped-def]
    vk = getattr(key, "vk", None)
    if preset_id == "right_ctrl":
        return key == keyboard.Key.ctrl_r or vk == 163
    if preset_id == "left_ctrl":
        return key == keyboard.Key.ctrl_l or vk == 162
    if preset_id == "right_alt":
        return key == keyboard.Key.alt_r or vk == 165
    if preset_id == "left_alt":
        return key == keyboard.Key.alt_l or vk == 164
    if preset_id == "space":
        return key == keyboard.Key.space or vk == 32
    return False


def keyboard_matches_spec(spec: str, key) -> bool:  # type: ignore[no-untyped-def]
    ns = normalize_spec(spec)
    if ns.startswith("mouse:"):
        return False
    if ns.startswith("vk:"):
        try:
            want = int(ns.split(":", 1)[1], 0)
        except ValueError:
            return False
        return getattr(key, "vk", None) == want
    return keyboard_matches_preset(ns, key)


def mouse_matches_spec(spec: str, button: mouse.Button) -> bool:
    return mouse_spec_to_button(spec) == button


def keyboard_token_for_event(key) -> str:  # type: ignore[no-untyped-def]
    vk = getattr(key, "vk", None)
    if vk is not None:
        return f"vk:{int(vk)}"
    return f"key:{repr(key)}"


def mouse_token_for_button(button: mouse.Button) -> str:
    s = mouse_button_to_spec(button)
    return s if s is not None else f"mouse:{repr(button)}"


def spec_label(spec: str) -> str:
    ns = normalize_spec(spec)
    if ns.startswith("vk:"):
        try:
            n = int(ns.split(":", 1)[1], 0)
        except ValueError:
            return ns
        return f"Key (virtual key {n})"
    if ns.startswith("mouse:"):
        tail = ns.split(":", 1)[1]
        pretty = {
            "x1": "Mouse button 4 (back)",
            "x2": "Mouse button 5 (forward)",
            "middle": "Middle mouse",
            "left": "Left mouse",
            "right": "Right mouse",
        }.get(tail, tail)
        return pretty
    return _PRESET_LABELS.get(ns, ns)


def specs_summary_phrase(specs: list[str]) -> str:
    """Short phrase for help/tooltip (e.g. one key vs several)."""
    norm = normalize_spec_list(specs)
    if len(norm) == 1:
        return spec_label(norm[0])
    parts = [spec_label(s) for s in norm[:4]]
    if len(norm) > 4:
        parts.append("…")
    return " or ".join(parts)


def event_matches_any_spec_keyboard(specs: list[str], key) -> bool:  # type: ignore[no-untyped-def]
    for s in specs:
        if keyboard_matches_spec(s, key):
            return True
    return False


def event_matches_any_spec_mouse(specs: list[str], button: mouse.Button) -> bool:
    for s in specs:
        if mouse_matches_spec(s, button):
            return True
    return False


def needs_keyboard_listener(specs: list[str]) -> bool:
    for s in specs:
        ns = normalize_spec(s)
        if not ns.startswith("mouse:"):
            return True
    return False


def needs_mouse_listener(specs: list[str]) -> bool:
    for s in specs:
        if normalize_spec(s).startswith("mouse:"):
            return True
    return False


def keyboard_event_to_capture_spec(key) -> Optional[str]:  # type: ignore[no-untyped-def]
    """Prefer a named preset when the key matches; else vk:NN."""
    vk = getattr(key, "vk", None)
    if vk == 27:  # Escape — cancel in capture UI, not stored
        return None
    for preset in _PRESET_IDS:
        if keyboard_matches_preset(preset, key):
            return preset
    if vk is not None:
        return f"vk:{int(vk)}"
    try:
        from pynput.keyboard import KeyCode

        if isinstance(key, KeyCode) and key.vk is not None:
            return f"vk:{int(key.vk)}"
    except Exception:
        pass
    return None
