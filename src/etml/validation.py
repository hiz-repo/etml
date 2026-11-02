"""Minimum-spec content models and work/document boundaries."""

import re

from .model import Diagnostic, DocumentUnit, Node, ParseError, Span, Work, WHITESPACE
from .schema import MIXED, RANGES, SCALARS


def _diagnostic(work: Work, message: str, node: Node | None = None) -> Diagnostic:
    span = node.span if node else work.source.span(len(work.source.text), len(work.source.text))
    return Diagnostic("structure", message, line=span.line, column=span.column,
                      byte_offset=span.start)


def _gap(node: Node) -> bool:
    return node.kind == "comment" or (node.kind == "text" and not (node.text or "").strip(WHITESPACE))


def _units(work: Work) -> tuple[DocumentUnit, ...]:
    nodes = [node for node in work.children if not _gap(node)]
    index = 0
    units = []

    def expect(kind: str, name: str | None = None) -> Node:
        nonlocal index
        node = nodes[index] if index < len(nodes) else None
        if node is None or node.kind != kind or (name is not None and node.name != name):
            raise ParseError(_diagnostic(work, "文書単位の順序または必須構造が不正です。", node))
        index += 1
        return node

    while index < len(nodes):
        if units:
            while index < len(nodes) and nodes[index].kind == "element" and nodes[index].name == "null":
                index += 1
            if index == len(nodes):
                raise ParseError(_diagnostic(work, "null の後には文書単位が必要です。"))
        part = expect("part") if nodes[index].kind == "part" else None
        declaration = expect("declaration")
        doctype = expect("doctype")
        root = expect("element", "etml")
        first = part or declaration
        units.append(DocumentUnit(Span(first.span.start, root.span.end,
                                       first.span.line, first.span.column),
                                  part, declaration, doctype, root))
    if not units:
        raise ParseError(_diagnostic(work, "作品には少なくとも一つの文書単位が必要です。"))
    return tuple(units)


def _elements(work: Work) -> None:
    for node in work.walk():
        if node.kind != "element":
            continue
        children = [child for child in node.children if not _gap(child)]
        name = node.name
        modifiers = node.modifiers
        if name == "body" or name in RANGES | {"movie", "log", "limit", "notes"}:
            bad = next((c for c in children if c.kind != "text"
                        and not (c.kind == "element" and c.name in MIXED)), None)
            if bad:
                raise ParseError(_diagnostic(work, "混在内容Mに置けない子があります。", bad))
            continue
        if name in SCALARS | {"null"}:
            bad = next((c for c in children if c.kind != "text"), None)
            if bad:
                raise ParseError(_diagnostic(work, "この要素の内容は通常本文だけです。", bad))
            continue
        if name == "flashback":
            bad = next((c for c in children if c.kind != "text"
                        and not (c.kind == "atom" and c.name == "re")), None)
            if bad:
                raise ParseError(_diagnostic(work, "flashback には本文と re だけを置けます。", bad))
            if not any(c.kind == "atom" for c in children):
                raise ParseError(_diagnostic(work, "flashback には re が必要です。", node))
            continue
        # A signature records kind as well as name: i cannot become an element.
        keys = []
        for child in children:
            if child.kind == "atom":
                keys.append(child.name)
            elif child.kind == "anonymous":
                keys.append("Anon")
            elif child.kind == "element" and child.name in SCALARS | {"body"}:
                keys.append(child.name)
            else:
                raise ParseError(_diagnostic(work, "項目列に置けない内容があります。", child))
        signature = " ".join(keys)
        if name == "etml":
            pattern = "body"
        elif name == "list":
            atom = {(): "i", ("item",): "i", ("dialogue",): "d", ("protocol",): "p",
                    ("company",): "c", ("meal",): "m", ("action",): "a"}[modifiers]
            pattern = atom + "(?: " + atom + ")*"
        elif name == "declaration":
            pattern = {(): r"(?:i(?: i)*|Anon(?: Anon)*)",
                       ("calculation",): r"pls(?: pls)*",
                       ("anger",): r"Anon(?: Anon)*"}[modifiers]
        elif name in {"theorem", "landscape"}:
            pattern = r"i(?: i)*"
        elif name == "commonsense":
            pattern = r"i(?: i)* ex"
        elif name == "question":
            pattern = "q a"
        elif name == "definition":
            pattern = r"i(?: d)+(?: i(?: d)+)*"
        elif name == "dictionary":
            pattern = r"item description(?: item description)*"
        elif name == "reference":
            pattern = "content" if modifiers == ("textbook",) else r"title author(?: author)*"
        elif name == "music":
            pattern = r"Anon(?: Anon)*"
        else:
            raise ParseError(_diagnostic(work, "未定義の内容モデルです。", node))
        if not re.fullmatch(pattern, signature):
            raise ParseError(_diagnostic(work, "子の種類・順序・個数が内容モデルに適合しません。", node))


def check_structure(work: Work) -> tuple[DocumentUnit, ...]:
    """Validate a parsed tree, returning its document-unit associations."""
    units = _units(work)
    _elements(work)
    return units


def validate_structure(work: Work) -> list[Diagnostic]:
    try:
        check_structure(work)
    except ParseError as exc:
        return [exc.diagnostic]
    return []


def validate_semantics(work: Work) -> list[Diagnostic]:
    return validate_structure(work) or [Diagnostic(
        "unavailable", "意味検証はこの処理系では未実装です。",
    )]
