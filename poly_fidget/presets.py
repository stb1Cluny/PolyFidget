"""Preset files: bundled (read-only) and user presets, plus the active preset.

The active preset is the one last applied, saved or renamed in this
session. The panel shows its name, and Rename / Delete act on it.
"""

import os

import bpy

ROOT_PACKAGE = __package__
BUNDLED_DIR = os.path.join(os.path.dirname(__file__), "assets", "presets")

_FORBIDDEN = set('<>:"/\\|?*')
_active = ""    # path of the active preset file, or ""


def user_dir():
    try:
        return bpy.utils.extension_path_user(ROOT_PACKAGE, path="presets", create=True)
    except ValueError:  # installed as a legacy add-on
        return bpy.utils.user_resource('CONFIG', path="poly_fidget_presets", create=True)


def files(folder):
    if not os.path.isdir(folder):
        return []
    return sorted(os.path.join(folder, f) for f in os.listdir(folder) if f.endswith(".json"))


def label(path):
    return bpy.path.display_name(os.path.basename(path))


def user_path(name):
    """Path of the user preset file for a display name; "" if the name is empty.

    The name keeps its case and punctuation; spaces become underscores, which
    ``label`` turns back into spaces, and characters Windows forbids are dropped.
    """
    stem = "".join(c for c in name.strip() if c not in _FORBIDDEN and ord(c) >= 32)
    stem = "_".join(stem.strip(" .").split())
    return os.path.join(user_dir(), stem + ".json") if stem.strip("_") else ""


def bundled_labels():
    return {label(p).lower() for p in files(BUNDLED_DIR)}


def is_user(path):
    return bool(path) and os.path.dirname(os.path.abspath(path)) == os.path.abspath(user_dir())


def active():
    if _active and not os.path.isfile(_active):
        set_active("")
    return _active


def active_user():
    path = active()
    return path if is_user(path) else ""


def set_active(path):
    global _active
    _active = path
