#!/usr/bin/env python3
"""Check annotated stories, preserved prose, and lossless ETML round trips.

Run from any directory: python3 /path/to/etml/scripts/check_story_examples.py
Add --show to inspect ranges, or --tests to run the complete test suite.
"""

import argparse
from collections import Counter
from hashlib import sha256
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from etml import Node, ParseError, Work, parse

# UTF-8 hashes of the accepted narrative text, including whitespace.
TEXT_SHA256 = {
    "mikan.etml": "4a408a399cb662af24a9a8fa3df1d2079c62e2c93af0c118fcb92ebd14101a11",
    "the_gift_of_the_magi.etml": "02318860b19912c79ee9085aae7d241b3774c4ab93a8c0bb1841d9989d4cb39b",
}


class CheckError(ValueError):
    """The example does not satisfy its preservation or annotation contract."""


def narrative_text(node: Node) -> str:
    """Extract these examples' narrative, including standalone-item payloads."""
    parts = []
    for child in node.walk():
        if child.kind == "text":
            parts.append(child.text or "")
        elif child.kind in {"atom", "anonymous"}:
            parts.append(child.payload or "")
    return "".join(parts)


def bodies(work: Work) -> tuple[Node, ...]:
    return tuple(next(child for child in unit.root.children
                      if child.kind == "element" and child.name == "body")
                 for unit in work.units)


def check_file(path: Path, expected_digest: str) -> tuple[Work, tuple[Node, ...]]:
    data = path.read_bytes()
    work = parse(data)  # Includes full header and structural validation.
    if work.serialize() != data:
        raise CheckError("lossless serialization differs from the input")
    text = "".join(narrative_text(body) for body in bodies(work))
    if sha256(text.encode("utf-8")).hexdigest() != expected_digest:
        raise CheckError("narrative text differs from the accepted baseline")
    annotations = tuple(child for body in bodies(work) for child in body.walk()
                        if child is not body and child.kind in {"element", "atom", "anonymous"})
    if not annotations:
        raise CheckError("no ETML annotations found in the story")
    return work, annotations


def main(argv: list[str] | None = None) -> int:
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--show", action="store_true", help="show annotated text excerpts")
    cli.add_argument("--tests", action="store_true", help="also run the complete test suite")
    args = cli.parse_args(argv)
    failed = False
    for name, digest in TEXT_SHA256.items():
        path = ROOT / "examples" / name
        try:
            _, annotations = check_file(path, digest)
        except ParseError as exc:
            d = exc.diagnostic
            print(f"FAIL {name}: {d.code} at {d.line}:{d.column}: {d.message}", file=sys.stderr)
            failed = True
            continue
        except (OSError, CheckError) as exc:
            print(f"FAIL {name}: {exc}", file=sys.stderr)
            failed = True
            continue
        counts = Counter(n.name or "anonymous" for n in annotations)
        print(f"PASS {name}: {len(annotations)} annotations; prose unchanged; round trip identical")
        print("  " + ", ".join(f"{tag}={count}" for tag, count in sorted(counts.items())))
        if args.show:
            for node in annotations:
                excerpt = " ".join(narrative_text(node).split())
                if len(excerpt) > 110:
                    excerpt = excerpt[:107] + "..."
                print(f"  {node.span.line}:{node.span.column} <{node.name or 'anonymous'}> {excerpt}")
    if failed:
        return 1
    if args.tests:
        sys.stdout.flush()
        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT / "src") + os.pathsep + env.get("PYTHONPATH", "")
        return subprocess.run(
            [sys.executable, "-m", "unittest", "discover", "-s", str(ROOT / "tests"), "-v"],
            cwd=ROOT, env=env, check=False,
        ).returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
