"""Fetch the public model files once; inference then uses local paths only."""
import argparse
import hashlib
import json
from pathlib import Path
import urllib.request

RELEASE = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.1/"


def fetch(url, destination):
    if destination.exists():
        return
    part = destination.with_suffix(destination.suffix + ".part")
    print(f"Downloading {destination.name}", flush=True)
    with urllib.request.urlopen(url, timeout=60) as response, part.open("wb") as out:
        while chunk := response.read(1024 * 1024):
            out.write(chunk)
    part.replace(destination)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="base.en", choices=["tiny.en", "base.en", "small.en"])
    parser.add_argument("--directory", type=Path, default=Path(__file__).resolve().parents[1] / "models")
    args = parser.parse_args()
    root = args.directory.resolve()
    root.mkdir(parents=True, exist_ok=True)
    for name in ("kokoro-v1.0.onnx", "voices-v1.0.bin"):
        fetch(RELEASE + name, root / name)
    from huggingface_hub import snapshot_download
    snapshot_download(f"Systran/faster-whisper-{args.model}", local_dir=root / "whisper",
                      allow_patterns=["*.json", "*.bin", "*.txt"])
    files = {}
    for p in root.rglob("*"):
        if p.is_file() and ".cache" not in p.parts and p.name != "manifest.json":
            with p.open("rb") as source:
                files[str(p.relative_to(root))] = hashlib.file_digest(source, "sha256").hexdigest()
    (root / "manifest.json").write_text(json.dumps({
        "whisper": f"Systran/faster-whisper-{args.model}", "kokoro_source": RELEASE,
        "sha256": files}, indent=2) + "\n")
    print(f"Models ready in {root}. Run: ova serve --profile local --models {root}")


if __name__ == "__main__":
    main()
