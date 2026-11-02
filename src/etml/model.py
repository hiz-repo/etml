"""Immutable, source-preserving ETML document model."""

from bisect import bisect_right
from dataclasses import asdict, dataclass, field
from typing import Iterator

WHITESPACE = " \t\r\n"


@dataclass(frozen=True)
class Span:
    """Half-open UTF-8 byte range; line/column count Unicode scalars."""
    start: int
    end: int
    line: int
    column: int


@dataclass(frozen=True)
class Diagnostic:
    code: str
    message: str
    path: str = "/"
    line: int | None = None
    column: int | None = None
    byte_offset: int | None = None


class ParseError(ValueError):
    def __init__(self, diagnostic: Diagnostic):
        self.diagnostic = diagnostic
        super().__init__(diagnostic.message)


@dataclass(frozen=True)
class Source:
    data: bytes = field(repr=False)
    text: str = field(repr=False)
    bom: bool
    _offsets: tuple[int, ...] = field(repr=False)
    _lines: tuple[int, ...] = field(repr=False)

    @classmethod
    def decode(cls, data: bytes) -> "Source":
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ParseError(Diagnostic(
                "encoding", "入力は正しいUTF-8でなければなりません。",
                byte_offset=exc.start,
            )) from exc
        bom = text.startswith("\ufeff")
        offsets = [0]
        lines = [1 if bom else 0]
        previous_cr = False
        for index, char in enumerate(text):
            offsets.append(offsets[-1] + len(char.encode("utf-8")))
            if char == "\r":
                lines.append(index + 1)
            elif char == "\n":
                if previous_cr:
                    lines[-1] = index + 1
                else:
                    lines.append(index + 1)
            previous_cr = char == "\r"
        source = cls(data, text, bom, tuple(offsets), tuple(lines))
        for index, char in enumerate(text):
            if ord(char) < 0x20 and char not in "\t\r\n":
                raise ParseError(source.diagnostic(
                    "encoding", "入力に許可されていない制御文字があります。", index,
                ))
        return source

    def span(self, start: int, end: int) -> Span:
        line_index = max(0, bisect_right(self._lines, start) - 1)
        column = max(1, start - self._lines[line_index] + 1)
        return Span(self._offsets[start], self._offsets[end], line_index + 1, column)

    def diagnostic(self, code: str, message: str, index: int) -> Diagnostic:
        span = self.span(index, index)
        return Diagnostic(code, message, line=span.line, column=span.column,
                          byte_offset=span.start)


@dataclass(frozen=True)
class HeaderPart:
    kind: str  # modifier, attribute, marker (playtime), value (after playtime)
    name: str | None
    value: str | None
    span: Span
    value_span: Span | None = None


@dataclass(frozen=True)
class Token:
    kind: str
    raw: str
    span: Span
    name: str | None = None
    header: tuple[HeaderPart, ...] = ()
    payload: str | None = None
    payload_span: Span | None = None


@dataclass(frozen=True)
class Node:
    kind: str
    span: Span
    name: str | None = None
    header: tuple[HeaderPart, ...] = ()
    children: tuple["Node", ...] = ()
    text: str | None = None
    payload: str | None = None
    payload_span: Span | None = None
    header_text: str | None = None
    header_text_span: Span | None = None
    opening_span: Span | None = None
    closing_span: Span | None = None

    @property
    def attributes(self) -> dict[str, str]:
        return {p.name: p.value for p in self.header
                if p.kind == "attribute" and p.name is not None and p.value is not None}

    @property
    def modifiers(self) -> tuple[str, ...]:
        return tuple(p.name for p in self.header
                     if p.kind == "modifier" and p.name is not None)

    def walk(self) -> Iterator["Node"]:
        pending = [self]
        while pending:
            node = pending.pop()
            yield node
            pending.extend(reversed(node.children))

    def to_dict(self) -> dict:
        result: dict = {}
        pending = [(self, result)]
        while pending:
            node, target = pending.pop()
            target.update(kind=node.kind, span=asdict(node.span))
            if node.name is not None:
                target["name"] = node.name
            if node.header:
                target["header"] = [asdict(part) for part in node.header]
            for key in ("text", "payload", "header_text"):
                value = getattr(node, key)
                if value is not None:
                    target[key] = value
            for key in ("payload_span", "header_text_span", "opening_span", "closing_span"):
                value = getattr(node, key)
                if value is not None:
                    target[key] = asdict(value)
            if node.kind == "element":
                children = [{} for _ in node.children]
                target["children"] = children
                pending.extend(zip(reversed(node.children), reversed(children)))
        return result


@dataclass(frozen=True)
class DocumentUnit:
    span: Span
    part: Node | None
    declaration: Node
    doctype: Node
    root: Node


@dataclass(frozen=True)
class TextSlot:
    kind: str
    name: str | None
    value: str
    span: Span


@dataclass(frozen=True)
class Work:
    source: Source = field(repr=False)
    children: tuple[Node, ...]
    tokens: tuple[Token, ...] = field(repr=False)
    units: tuple[DocumentUnit, ...] = ()

    def walk(self) -> Iterator[Node]:
        for node in self.children:
            yield from node.walk()

    def text_slots(self) -> Iterator[TextSlot]:
        """Distinct source-ordered slots, not a flattened reading order."""
        for node in self.walk():
            if node.kind == "text":
                yield TextSlot("text", None, node.text or "", node.span)
            elif node.kind in {"atom", "anonymous"}:
                assert node.payload_span is not None
                yield TextSlot(node.kind, node.name, node.payload or "", node.payload_span)
            elif node.header_text is not None:
                assert node.header_text_span is not None
                yield TextSlot("header-text", node.name, node.header_text,
                               node.header_text_span)

    def serialize(self) -> bytes:
        """Reassemble unedited source from its lexical tokens, including BOM."""
        prefix = b"\xef\xbb\xbf" if self.source.bom else b""
        return prefix + "".join(token.raw for token in self.tokens).encode("utf-8")

    def to_dict(self) -> dict:
        indices = {id(node): index for index, node in enumerate(self.children)}
        return {
            "kind": "work", "bom": self.source.bom,
            "span": asdict(self.source.span(0, len(self.source.text))),
            "children": [node.to_dict() for node in self.children],
            "units": [{
                "span": asdict(unit.span),
                "part": indices[id(unit.part)] if unit.part else None,
                "declaration": indices[id(unit.declaration)],
                "doctype": indices[id(unit.doctype)],
                "root": indices[id(unit.root)],
            } for unit in self.units],
        }
