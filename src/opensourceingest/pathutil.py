"""Safe path handling for archives and local dataset roots."""

from __future__ import annotations

from pathlib import Path


def is_safe_zip_member(name: str) -> bool:
    if not name or name.startswith("/") or ".." in Path(name).parts:
        return False
    return True


def ensure_within_directory(base: Path, target: Path) -> Path:
    base_r = base.resolve()
    full = (base_r / target).resolve()
    if not full.is_relative_to(base_r):
        raise ValueError("Path traversal detected")
    return full
