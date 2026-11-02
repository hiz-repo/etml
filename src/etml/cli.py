"""Command-line reader, validator, text-slot inspector and lossless serializer."""

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys

from .model import ParseError
from .parser import MAX_BYTES, parse
from .validation import validate_semantics


def emit(value: object, *, stream=None) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2), file=stream or sys.stdout)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="ETML 最小構文仕様の読取り処理系")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("parse", "text", "validate", "roundtrip"):
        command = commands.add_parser(name)
        command.add_argument("file", type=Path)
        if name == "validate":
            command.add_argument("--level", choices=("structure", "semantic"), default="structure")
        if name == "roundtrip":
            command.add_argument("-o", "--output", type=Path)
    args = parser.parse_args(argv)
    try:
        with args.file.open("rb") as source:
            work = parse(source.read(MAX_BYTES + 1))
        if args.command == "parse":
            emit(work.to_dict())
        elif args.command == "text":
            emit({"slots": [asdict(slot) for slot in work.text_slots()]})
        elif args.command == "roundtrip":
            data = work.serialize()
            if args.output:
                args.output.write_bytes(data)
            else:
                sys.stdout.buffer.write(data)
        else:
            diagnostics = validate_semantics(work) if args.level == "semantic" else []
            emit({"frontend": "etml", "level": args.level,
                  "status": "unavailable" if diagnostics else "valid",
                  "diagnostics": [asdict(d) for d in diagnostics]})
            return 3 if diagnostics else 0
    except OSError as exc:
        emit({"code": "io", "message": str(exc)}, stream=sys.stderr)
        return 2
    except ParseError as exc:
        diagnostic = asdict(exc.diagnostic)
        if args.command == "validate":
            emit({"frontend": "etml", "level": args.level, "status": "invalid",
                  "diagnostics": [diagnostic]})
        else:
            emit(diagnostic, stream=sys.stderr)
        return 1
    return 0
