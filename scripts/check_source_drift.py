"""Read-only check: has Claude changed a lab since this independent export was made?"""
import hashlib
import json
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1]
book = root.parent
if not (book / "code-labs").is_dir():
    raise SystemExit("Run beside the authoring project; published clones use the saved snapshot.")
manifest = json.loads((root / "docs/source-snapshot.json").read_text())
changed = []
for row in manifest["files"]:
    if row["destination"].startswith("chapters/"):
        source = book / row["source"]
        if not source.exists() or hashlib.sha256(source.read_bytes()).hexdigest() != row["sha256"]:
            changed.append(row["source"])
print("\n".join(changed) if changed else "Chapter sources still match the export snapshot.")
sys.exit(bool(changed))
