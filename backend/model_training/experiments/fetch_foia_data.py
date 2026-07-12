"""Fetch the SBA 7(a) FOIA loan-level files used by the experiment suite.

The files are official U.S. SBA FOIA releases (public domain). The live
data.sba.gov portal removed the loan-level pages during its 2026 migration, so
the pinned, hash-verified copies are retrieved from the Internet Archive's
January 2026 capture. ~740 MB total; they stay in the gitignored
`model_training/data/` directory — only this script and the manifest are
committed.

Run:  python backend/model_training/experiments/fetch_foia_data.py
"""
from __future__ import annotations

import hashlib
import json
import sys
import urllib.request
from pathlib import Path

HERE = Path(__file__).parent
DATA_DIR = HERE.parent / "data"
MANIFEST_PATH = HERE / "foia_manifest.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    DATA_DIR.mkdir(exist_ok=True)
    failures = []
    for item in manifest["files"]:
        target = DATA_DIR / item["filename"]
        if not target.exists():
            print(f"Downloading {item['filename']} ({item['bytes']:,} bytes) ...")
            urllib.request.urlretrieve(item["archive_url"], target)  # noqa: S310 (pinned https URL from committed manifest)
        actual = sha256(target)
        if actual != item["sha256"]:
            failures.append(f"{item['filename']}: expected {item['sha256']}, got {actual}")
        else:
            print(f"OK  {item['filename']}  sha256={actual[:12]}...  rows={item['rows']:,}")
    if failures:
        raise SystemExit("Integrity check failed:\n" + "\n".join(failures))
    print("All FOIA files verified.")


if __name__ == "__main__":
    sys.exit(main())
