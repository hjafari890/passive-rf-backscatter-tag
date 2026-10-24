"""Verification test for documentation asset links."""

from __future__ import annotations

import os
import re
import pytest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
README_PATH = os.path.join(REPO_ROOT, "README.md")


def test_readme_embedded_images_exist() -> None:
    """Verify that all markdown image references in README.md exist as non-empty files."""
    assert os.path.isfile(README_PATH), f"README missing at {README_PATH}"

    with open(README_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    # Match ![alt](path)
    img_matches = re.findall(r"!\[.*?\]\((docs/assets/[^)]+)\)", content)
    assert len(img_matches) > 0, "No docs/assets/ image references found in README.md"

    for img_rel in img_matches:
        img_abs = os.path.join(REPO_ROOT, img_rel.replace("/", os.sep))
        assert os.path.isfile(img_abs), f"Broken image link in README.md: {img_rel} (path: {img_abs})"
        assert os.path.getsize(img_abs) > 1000, f"Image file is suspiciously small or empty: {img_rel}"
