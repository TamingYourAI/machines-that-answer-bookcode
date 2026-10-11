"""Export a source-only release from explicit directories, without local models or data."""
import argparse
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
APP_FILES = {"README.md", "LICENSE", "PLAN.md", "REQUIREMENTS.md", "pyproject.toml",
             "requirements.lock", "Dockerfile", "compose.yaml", ".env.example",
             ".gitignore", ".dockerignore"}
OMIT = {"__pycache__", ".pytest_cache", ".DS_Store", ".venv", "node_modules", "eval-results"}


def release_files():
    for name in ("README.md", "LICENSE", ".gitignore"):
        yield ROOT / name
    for folder in ("chapters", "docs", "evals", "scripts", ".github", "full-app"):
        for path in sorted((ROOT / folder).rglob("*")):
            rel = path.relative_to(ROOT)
            if not path.is_file() or path.is_symlink() or OMIT.intersection(rel.parts):
                continue
            if path.suffix in {".pyc", ".pyo", ".sqlite3"}:
                continue
            if rel.parts[:2] == ("docs", "specs"):       # internal design notes stay private
                continue
            if path.name.startswith(".env") and path.name != ".env.example":
                continue
            if folder == "full-app":
                inside = path.relative_to(ROOT / folder)
                if inside.parts[0] not in {"src", "tests", "docs"} and str(inside) not in APP_FILES:
                    continue
                if any(part.endswith(".egg-info") for part in inside.parts):
                    continue
            yield path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path,
                        default=ROOT / "dist/open-voice-agents-0.3.2.zip")
    args = parser.parse_args()
    files = list(release_files())
    required = ROOT / "full-app/src/ova_apps/claims/data/policies.json"
    if required not in files:
        raise SystemExit("Synthetic policies missing from release")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(args.output, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            archive.write(path, Path("open-voice-agents") / path.relative_to(ROOT))
    print(f"Exported {len(files)} source files to {args.output}")


if __name__ == "__main__":
    main()
