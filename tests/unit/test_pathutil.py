from pathlib import Path

import pytest

from opensourceingest.pathutil import ensure_within_directory, is_safe_zip_member


def test_zip_member_blocks_traversal():
    assert is_safe_zip_member("ok/path/file.jpg") is True
    assert is_safe_zip_member("../evil.jpg") is False
    assert is_safe_zip_member("/abs.jpg") is False


def test_ensure_within_directory():
    base = Path("/tmp")
    target = Path("safe/sub.jpg")
    resolved = ensure_within_directory(base, target)
    assert str(resolved).startswith(str(base.resolve()))


def test_ensure_within_directory_raises():
    with pytest.raises(ValueError):
        ensure_within_directory(Path("/tmp"), Path("../etc/passwd"))
