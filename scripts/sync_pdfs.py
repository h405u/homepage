#!/usr/bin/env python3
"""Copy locally configured PDFs into the site's tracked pdfs directory."""

from __future__ import annotations

import argparse
import filecmp
import json
import shutil
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG = REPO_ROOT / "pdfs.local.json"
PDF_DIR = REPO_ROOT / "pdfs"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Copy PDFs listed in a private JSON map into the site."
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG,
        help="JSON file mapping local source paths to destination PDF names",
    )
    parser.add_argument(
        "--stage",
        action="store_true",
        help="stage copied PDFs for the current commit",
    )
    return parser.parse_args()


def load_pdf_map(config_path: Path) -> dict[str, str] | None:
    if not config_path.exists():
        print(f"PDF sync skipped: {config_path.name} does not exist.")
        return None

    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"Could not read {config_path}: {error}") from error

    if not isinstance(data, dict):
        raise ValueError(f"{config_path} must contain a JSON object.")

    for source, destination in data.items():
        if not isinstance(source, str) or not isinstance(destination, str):
            raise ValueError("Every PDF source and destination must be a string.")

    return data


def validate_destination(name: str) -> str:
    destination = Path(name)
    if destination.name != name or destination.suffix.lower() != ".pdf":
        raise ValueError(
            f"Invalid destination {name!r}; use a simple filename ending in .pdf."
        )
    return name


def copy_pdfs(pdf_map: dict[str, str]) -> list[Path]:
    copied: list[Path] = []
    PDF_DIR.mkdir(exist_ok=True)

    for source_address, destination_name in pdf_map.items():
        source = Path(source_address).expanduser()
        validate_destination(destination_name)

        if source.suffix.lower() != ".pdf":
            raise ValueError(f"Source is not a PDF: {source}")
        if not source.is_file():
            raise FileNotFoundError(f"PDF source does not exist: {source}")

        destination = PDF_DIR / destination_name
        if destination.exists() and filecmp.cmp(source, destination, shallow=False):
            print(f"Already current: pdfs/{destination_name}")
        else:
            shutil.copy2(source, destination)
            print(f"Copied {source} -> pdfs/{destination_name}")
        copied.append(destination)

    return copied


def stage_pdfs(paths: list[Path]) -> None:
    if not paths:
        return
    relative_paths = [str(path.relative_to(REPO_ROOT)) for path in paths]
    subprocess.run(
        ["git", "add", "--", *relative_paths],
        cwd=REPO_ROOT,
        check=True,
    )
    print("Staged synced PDFs for this commit.")


def main() -> int:
    args = parse_args()
    config_path = args.config.expanduser().resolve()

    try:
        pdf_map = load_pdf_map(config_path)
        if pdf_map is None:
            return 0
        if not pdf_map:
            print(
                f"No PDFs configured. Add entries to {config_path.name}, for example:\n"
                '  {"/absolute/path/to/your/cv.pdf": "cv.pdf"}'
            )
            return 0
        copied = copy_pdfs(pdf_map)
        if args.stage:
            stage_pdfs(copied)
    except (FileNotFoundError, OSError, ValueError, subprocess.CalledProcessError) as error:
        print(f"PDF sync failed: {error}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
