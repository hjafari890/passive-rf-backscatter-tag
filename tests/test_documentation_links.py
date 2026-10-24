"""Verification test for documentation asset links and path sanitization."""

from __future__ import annotations

import os
import re
import pytest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
README_PATH = os.path.join(REPO_ROOT, "README.md")
DOCS_DIR = os.path.join(REPO_ROOT, "docs")


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


def test_docs_markdown_embedded_images_exist() -> None:
    """Verify that all image references in docs/*.md point to existing asset files."""
    assert os.path.isdir(DOCS_DIR), f"Docs directory missing at {DOCS_DIR}"

    doc_files = [os.path.join(DOCS_DIR, f) for f in os.listdir(DOCS_DIR) if f.endswith(".md")]
    assert len(doc_files) > 0, "No markdown files found in docs/"

    found_images = 0
    for doc_path in doc_files:
        with open(doc_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Match ![alt](assets/...) or ![alt](docs/assets/...)
        img_matches = re.findall(r"!\[.*?\]\(((?:docs/)?assets/[^)]+)\)", content)
        for img_rel in img_matches:
            found_images += 1
            if img_rel.startswith("docs/"):
                img_abs = os.path.join(REPO_ROOT, img_rel.replace("/", os.sep))
            else:
                img_abs = os.path.join(DOCS_DIR, img_rel.replace("/", os.sep))
            assert os.path.isfile(img_abs), f"Broken image link in {os.path.basename(doc_path)}: {img_rel} (path: {img_abs})"
            assert os.path.getsize(img_abs) > 1000, f"Image file is empty or too small: {img_rel}"

    assert found_images > 0, "No asset image references found across docs/*.md"


def test_no_machine_specific_paths_in_docs() -> None:
    """Verify that no machine-specific absolute paths or private directories leak into any markdown file in the repository."""
    files_to_check: list[str] = []
    ignored_dirs = {".git", ".pytest_cache", ".venv", "venv", ".agents"}
    for root, dirs, files in os.walk(REPO_ROOT):
        # Skip ignored directory trees
        dirs[:] = [d for d in dirs if d not in ignored_dirs]
        for f in files:
            if f.endswith(".md"):
                files_to_check.append(os.path.join(root, f))

    assert len(files_to_check) >= 4, f"Found too few markdown files to check: {len(files_to_check)}"

    forbidden_patterns = [
        r"[Cc]:\\Users\\hjafa",
        r"OneDrive\\Desktop",
        r"\.gemini[\\/]antigravity",
        r"file:///[A-Za-z]:",
    ]

    for fpath in files_to_check:
        with open(fpath, "r", encoding="utf-8") as f:
            content = f.read()

        for pat in forbidden_patterns:
            matches = re.findall(pat, content, re.IGNORECASE)
            assert len(matches) == 0, (
                f"Machine-specific path leak found in {os.path.relpath(fpath, REPO_ROOT)}: "
                f"matched '{pat}' {len(matches)} time(s)"
            )

