"""ETML minimum-syntax reader and source-preserving document model."""

from .model import Diagnostic, DocumentUnit, Node, ParseError, Span, TextSlot, Work
from .parser import Limits, parse

__version__ = "0.1.0"
__all__ = ["parse", "Limits", "Work", "Node", "DocumentUnit", "Span", "TextSlot",
           "Diagnostic", "ParseError"]
