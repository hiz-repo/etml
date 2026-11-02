"""Strict, lossless reader for the ETML minimum syntax specification."""

from dataclasses import dataclass, replace
import re
from typing import Iterator

from .model import Diagnostic, HeaderPart, Node, ParseError, Source, Span, Token, Work, WHITESPACE
from .schema import ATOMS, DECLARATION, DOCTYPE, HEADERS, NAMES, PAIRED

MAX_BYTES = 1024 * 1024
MAX_DEPTH = 256
MAX_NODES = 10_000
NAME = re.compile(r"[A-Za-z][A-Za-z0-9_-]*")


@dataclass(frozen=True)
class Limits:
    """Implementation limits, not language limits; depth counts etml as 1."""
    max_bytes: int = MAX_BYTES
    max_depth: int = MAX_DEPTH
    max_nodes: int = MAX_NODES

    def __post_init__(self):
        for value in (self.max_bytes, self.max_depth, self.max_nodes):
            if type(value) is not int or value < 1:
                raise ValueError("処理量上限には正の整数を指定してください。")


class _Lexer:
    def __init__(self, source: Source):
        self.source = source
        self.text = source.text

    def fail(self, code: str, message: str, index: int):
        raise ParseError(self.source.diagnostic(code, message, index))

    def end(self, start: int, marker: str, *, comment: bool = False,
            opener_length: int = 1) -> int:
        end = self.text.find(marker, start + opener_length)
        if not comment:
            nested = self.text.find("<", start + 1)
            if nested >= 0 and (end < 0 or nested < end):
                self.fail("syntax", "区切りが閉じる前に新たな < が現れました。", start)
        if end < 0:
            self.fail("unclosed", "字句の終端がありません。", start)
        return end + len(marker)

    @staticmethod
    def valid_value(value: str) -> bool:
        return bool(value) and not value.startswith(" ") and not value.endswith(" ") and not any(
            char in ":<>=\t\r\n" for char in value
        )

    def header(self, name: str, body: str, start: int) -> tuple[HeaderPart, ...]:
        tail = body[len(name):]
        if tail and not tail.startswith(":"):
            self.fail("syntax", "名前の直後の区切りが不正です。", start)
        pieces = tail[1:].split(":") if tail else []
        for form in HEADERS[name]:
            if len(form) != len(pieces):
                continue
            parts = []
            cursor = start + 1 + len(name) + 1
            for expected, piece in zip(form, pieces):
                kind = "modifier"
                key: str | None = piece
                value: str | None = None
                value_span = None
                if expected.startswith("@"):
                    key = expected[1:]
                    if not piece.startswith(key + "="):
                        break
                    value = piece[len(key) + 1:]
                    if not self.valid_value(value):
                        break
                    kind = "attribute"
                    value_span = self.source.span(cursor + len(key) + 1, cursor + len(piece))
                elif expected == "$":
                    if not self.valid_value(piece):
                        break
                    kind, key, value = "value", None, piece
                    value_span = self.source.span(cursor, cursor + len(piece))
                elif expected.startswith("!"):
                    if piece != expected[1:]:
                        break
                    kind = "marker"
                elif piece != expected:
                    break
                parts.append(HeaderPart(kind, key, value,
                                        self.source.span(cursor, cursor + len(piece)), value_span))
                cursor += len(piece) + 1
            else:
                return tuple(parts)
        self.fail("header", "ヘッダの部品・順序・値が仕様に適合しません。", start)
        raise AssertionError("unreachable")

    def payload(self, start: int, end: int, token_start: int) -> tuple[str, Span]:
        value = self.text[start:end]
        if not value.strip(WHITESPACE):
            self.fail("payload", "本文には少なくとも一つの非空白文字が必要です。", token_start)
        return value, self.source.span(start, end)

    def __iter__(self) -> Iterator[Token]:
        pos = 1 if self.source.bom else 0
        text = self.text
        while pos < len(text):
            start = pos
            if text[pos] != "<":
                found = text.find("<", pos)
                pos = len(text) if found < 0 else found
                yield Token("text", text[start:pos], self.source.span(start, pos))
                continue
            if text.startswith("<!--", pos):
                pos = self.end(start, "-->", comment=True, opener_length=4)
                yield Token("comment", text[start:pos], self.source.span(start, pos),
                            payload=text[start + 4:pos - 3],
                            payload_span=self.source.span(start + 4, pos - 3))
                continue
            if text.startswith("<?", pos):
                pos = self.end(start, "?>", opener_length=2)
                if text[start:pos] != DECLARATION:
                    self.fail("declaration", "未対応の宣言です。", start)
                parts = []
                for key, value in (("version", "1.2"), ("encoding", "EMO-590378")):
                    offset = text.index(key + "=", start, pos)
                    value_start = offset + len(key) + 1
                    parts.append(HeaderPart("attribute", key, value,
                                            self.source.span(offset, value_start + len(value)),
                                            self.source.span(value_start, value_start + len(value))))
                yield Token("declaration", text[start:pos], self.source.span(start, pos),
                            header=tuple(parts))
                continue
            if text.startswith("<!", pos):
                pos = self.end(start, ">")
                if text[start:pos] != DOCTYPE:
                    self.fail("declaration", "未対応のDOCTYPEまたは宣言です。", start)
                yield Token("doctype", text[start:pos], self.source.span(start, pos))
                continue
            pos = self.end(start, ">")
            raw = text[start:pos]
            span = self.source.span(start, pos)
            if raw.startswith("</"):
                match = re.fullmatch(r"</([A-Za-z][A-Za-z0-9_-]*)>", raw)
                if not match:
                    self.fail("syntax", "終了タグは </基底名> の形に限ります。", start)
                name = match.group(1)
                if name not in NAMES:
                    self.fail("name", "未定義の名前です。", start)
                if name not in PAIRED:
                    self.fail("syntax", "この名前に終了タグはありません。", start)
                yield Token("end", raw, span, name=name)
                continue
            match = NAME.match(text, start + 1)
            if not match:
                value, value_span = self.payload(start + 1, pos - 1, start)
                yield Token("anonymous", raw, span, payload=value, payload_span=value_span)
                continue
            name = match.group()
            if text[match.end():pos] != "/>" and text[match.end()] not in ":>":
                self.fail("syntax", "名前の直後に不正な文字があります。", start)
            if name not in NAMES:
                self.fail("name", "未定義の名前です。", start)
            if name in ATOMS or name == "notes":
                if not raw.startswith("<" + name + ":"):
                    self.fail("header", "名前の後にコロンと本文が必要です。", start)
                value, value_span = self.payload(start + len(name) + 2, pos - 1, start)
                yield Token("atom" if name in ATOMS else "start", raw, span,
                            name=name, payload=value, payload_span=value_span)
                continue
            if name == "part":
                if not raw.endswith("/>"):
                    self.fail("syntax", "part は /> で閉じてください。", start)
                body = raw[1:-2]
                kind = "part"
            else:
                body = raw[1:-1]
                kind = "start"
            parts = self.header(name, body, start)
            yield Token(kind, raw, span, name=name, header=parts)


def _leaf(token: Token) -> Node:
    if token.kind in {"text", "comment"}:
        return Node(token.kind, token.span,
                    text=token.raw if token.kind == "text" else token.payload,
                    payload_span=token.span if token.kind == "text" else token.payload_span)
    return Node(token.kind, token.span, name=token.name, header=token.header,
                payload=token.payload, payload_span=token.payload_span)


def parse(data: bytes, *, limits: Limits | None = None) -> Work:
    """Read and validate an entire work; raise ParseError on the first failure."""
    if not isinstance(data, bytes):
        raise TypeError("parse() expects UTF-8 bytes")
    limits = limits or Limits()
    if len(data) > limits.max_bytes:
        prefix = data[:limits.max_bytes].decode("utf-8", errors="ignore")
        location = Source.decode(prefix.encode("utf-8")).span(len(prefix), len(prefix))
        raise ParseError(Diagnostic("limit", "入力バイト数の実装上限を超えました。",
                                   line=location.line, column=location.column,
                                   byte_offset=limits.max_bytes))
    source = Source.decode(data)
    tokens: list[Token] = []
    roots: list[Node] = []
    stack: list[tuple[Token, list[Node]]] = []
    count = 0
    for token in _Lexer(source):
        tokens.append(token)
        if token.kind == "end":
            if not stack or stack[-1][0].name != token.name:
                raise ParseError(Diagnostic("end-tag", "終了タグに対応する開始がありません。",
                                           line=token.span.line, column=token.span.column,
                                           byte_offset=token.span.start))
            opening, children = stack.pop()
            node = Node("element", Span(opening.span.start, token.span.end,
                                         opening.span.line, opening.span.column),
                        name=opening.name, header=opening.header, children=tuple(children),
                        header_text=opening.payload, header_text_span=opening.payload_span,
                        opening_span=opening.span, closing_span=token.span)
        else:
            count += 1
            if count > limits.max_nodes:
                raise ParseError(Diagnostic("limit", "ノード数の実装上限を超えました。",
                                           line=token.span.line, column=token.span.column,
                                           byte_offset=token.span.start))
            if token.kind == "start":
                if len(stack) >= limits.max_depth:
                    raise ParseError(Diagnostic("limit", "要素深さの実装上限を超えました。",
                                               line=token.span.line, column=token.span.column,
                                               byte_offset=token.span.start))
                stack.append((token, []))
                continue
            node = _leaf(token)
        (stack[-1][1] if stack else roots).append(node)
    if stack:
        opening = stack[-1][0]
        raise ParseError(Diagnostic("unclosed", "要素の終了タグがありません。",
                                   line=opening.span.line, column=opening.span.column,
                                   byte_offset=opening.span.start))
    work = Work(source, tuple(roots), tuple(tokens))
    from .validation import check_structure
    return replace(work, units=check_structure(work))
