"""Build docs/data/scores.json from a Paper Copilot ICLR 2027 snapshot.

Download a snapshot JSONL and its meta.json from the same archive commit at
https://github.com/papercopilot/openreview/tree/main/venues/iclr/iclr2027
and keep the source files under data/raw/.

    python3 scripts/build_scores.py SNAPSHOT.jsonl meta.json ARCHIVE_COMMIT_SHA
"""

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

OUT = Path(__file__).resolve().parent.parent / "docs" / "data" / "scores.json"


def read_ratings(snapshot, expected):
    digest = hashlib.sha256()
    seen, ratings = set(), {}
    with snapshot.open("rb") as stream:
        for line in stream:
            digest.update(line)
            paper = json.loads(line)
            forum = paper["id"]
            if not re.fullmatch(r"[A-Za-z0-9_-]+", forum) or forum in seen:
                raise ValueError(f"Invalid or repeated OpenReview forum ID: {forum}")
            seen.add(forum)

            values = [int(v) for v in (paper.get("rating") or "").split(";") if v]
            if any(v < 1 or v > 4 for v in values):
                raise ValueError(f"Rating outside the ICLR 2027 scale for {forum}")
            if values:
                ratings[forum] = sorted(values)

    total = sum(map(len, ratings.values()))
    if digest.hexdigest() != expected["sha256"]:
        raise ValueError("Snapshot SHA-256 does not match meta.json")
    if (len(seen), len(ratings), total) != (expected["papers"], expected["scored_papers"], expected["ratings"]):
        raise ValueError("Paper and rating counts do not match meta.json")
    return ratings, total


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("snapshot", type=Path)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("revision", help="40-character Git SHA of the Paper Copilot archive")
    args = parser.parse_args()
    if not re.fullmatch(r"[0-9a-f]{40}", args.revision):
        parser.error("revision must be a 40-character Git SHA")

    expected = json.loads(args.manifest.read_text())["snapshots"][args.snapshot.name]
    if (expected["conf"], expected["year"]) != ("iclr", 2027):
        parser.error("manifest must describe an ICLR 2027 snapshot")
    ratings, total = read_ratings(args.snapshot, expected)
    data = {
        "capturedAt": datetime.fromisoformat(expected["completed_at"]).astimezone(timezone.utc).isoformat(timespec="seconds"),
        "source": f"https://github.com/papercopilot/openreview/blob/{args.revision}/venues/iclr/iclr2027/meta.json",
        "ratings": dict(sorted(ratings.items())),
    }

    with TemporaryDirectory(dir=OUT.parent) as directory:
        staged = Path(directory) / OUT.name
        staged.write_text(json.dumps(data, separators=(",", ":")) + "\n", encoding="utf-8")
        staged.replace(OUT)
    print(f"Saved {total:,} ratings for {len(ratings):,} papers to {OUT}")


if __name__ == "__main__":
    main()
