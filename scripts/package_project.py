"""Create a clean, downloadable ZIP without local settings or generated files."""

from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT = PROJECT_ROOT / "dist" / "wealth-advisor-assistant.zip"
EXCLUDED_PARTS = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    "logs",
    "history",
    "dist",
}


def should_include(path: Path) -> bool:
    relative = path.relative_to(PROJECT_ROOT)
    if any(part in EXCLUDED_PARTS for part in relative.parts):
        return False
    if path.name == ".env" or path.name.endswith((".pyc", ".pyo")):
        return False
    if path.as_posix().endswith("outputs/generated_report.json"):
        return False
    return path.is_file()


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    files = sorted(path for path in PROJECT_ROOT.rglob("*") if should_include(path))
    with ZipFile(OUTPUT, "w", compression=ZIP_DEFLATED, compresslevel=9) as archive:
        for path in files:
            archive.write(
                path,
                arcname=Path(PROJECT_ROOT.name) / path.relative_to(PROJECT_ROOT),
            )
    print(f"Created {OUTPUT} ({len(files)} files)")


if __name__ == "__main__":
    main()
