<div align="center">

<h1>&lt;etml/&gt;</h1>

<p><strong>Emotion-in-Text Markup Language</strong></p>
<p>A literary language project inspired by <code>&lt;harmony/&gt;</code> by Project Itoh.</p>

<p>
  <img alt="Status: under development" src="https://img.shields.io/badge/status-under_development-7856A6?style=flat-square">
  <img alt="Specification: minimum syntax" src="https://img.shields.io/badge/spec-minimum_syntax-343A46?style=flat-square">
  <img alt="Python: 3.11 or later" src="https://img.shields.io/badge/python-3.11%2B-3776AB?style=flat-square">
  <a href="LICENSE"><img alt="License: MIT" src="https://img.shields.io/badge/license-MIT-5B8C85?style=flat-square"></a>
</p>

<br>

<p>
  <strong>Dedicated to Miach Mihie.</strong><br>
</p>

<p>
  <a href="#the-project">The project</a> ·
  <a href="#try-the-parser">Try the parser</a> ·
  <a href="#examples">Examples</a> ·
  <a href="#specification">Specification</a>
</p>

</div>

---

## The project

In *Harmony*, emotion becomes part of the language in which a story is written.
This project takes that idea as a starting point for a language that can be written, parsed, and studied.

**etml is a hobby project and a personal tribute to Project Itoh.** It explores the formal structure of literary expression through computer science and psychology, with three connected goals:

- A **complete language specification**, covering syntax, semantics, processing rules, and conformance.
- A **complete classification of emotion and cognition grounded in psychological theory**, developed as an essential part of the language.
- An **open implementation and shared tests**, connecting the specification to observable behavior.

The psychological theory and the final classification system are still to be selected.

## Current state

**Under development · Parser 0.1.0**

The parser implements the [minimum syntax specification](spec/spec.md): multiple documents, all 63 currently registered names, structural validation, source positions, and byte-for-byte round trips. The document model keeps ordinary text, standalone items, anonymous text, and the two text positions in `notes` distinct.

**Additional emotion elements and richer annotations are planned.** The vocabulary, specification, and implementation will continue to evolve as development proceeds.

The implementation uses Python's standard library. Input diagnostics include a category and byte offset, with line and column when available. `validate --level semantic` reports `unavailable` and returns exit code `3`.

## A first look

```etml
<?Emotion-in-Text Markup Language:version=1.2:encoding=EMO-590378?>
<!DOCTYPE etml PUBLIC :-//WENC/DTD ETML 1.2 transitional//EN>
<etml:lang=en>
<body>
The clock rang. <surprise>I looked up.</surprise>
<list:item><i: A key><i: A notebook></list>
<notes: An old name>North Square</notes> was our meeting place.
</body>
</etml>
```

This short example uses original text written for the project.

## Try the parser

Requires **Python 3.11+**. There are no additional runtime dependencies. Run these commands from the repository root:

```sh
# Inspect the document tree and document-unit associations as JSON.
PYTHONPATH=src python3 -m etml parse examples/mikan.etml

# Validate the Japanese and English story examples.
PYTHONPATH=src python3 -m etml validate examples/mikan.etml
PYTHONPATH=src python3 -m etml validate examples/the_gift_of_the_magi.etml

# Inspect distinct text slots as JSON.
PYTHONPATH=src python3 -m etml text examples/the_gift_of_the_magi.etml

# Reassemble the original bytes after parsing and validation.
PYTHONPATH=src python3 -m etml roundtrip examples/mikan.etml -o /tmp/mikan-copy.etml
```

`text` reports text slots in source order, including separate `notes` header text. `roundtrip` writes bytes to stdout when `-o` is omitted. Exit codes are `0` for success, `1` for invalid input or a processing limit, `2` for CLI or I/O errors, and `3` for unavailable semantic validation (`validate --level semantic`).

For the Python API, start an interpreter from the repository root with `PYTHONPATH=src python3`:

```python
from pathlib import Path
from etml import Limits, parse

source = Path("examples/mikan.etml").read_bytes()
work = parse(source, limits=Limits())
assert work.serialize() == source
for unit in work.units:
    print(unit.root.attributes["lang"])
for slot in work.text_slots():
    print(slot.kind, slot.value, slot.span)
```

Parsed nodes and header parts are immutable. Source ranges use half-open UTF-8 byte offsets; whitespace, LF/CRLF/CR, and an optional leading BOM are preserved. Default implementation limits are **1 MiB**, **256 nested elements**, and **10,000 nodes**. `Limits` configures Python API limits; the CLI uses the defaults.

Run the tests with `make test`, and check the annotated stories with `make example`.

## Examples

| File | Contents | Text rights |
| --- | --- | --- |
| [mikan.etml](examples/mikan.etml) | 芥川龍之介, *蜜柑* (*Mikan*), annotated Japanese text | Public domain in Japan; [source details](examples/README.md#mikan) |
| [the_gift_of_the_magi.etml](examples/the_gift_of_the_magi.etml) | O. Henry, *The Gift of the Magi*, annotated English text | Public domain in the USA; [source details](examples/README.md#the-gift-of-the-magi) |

The two stories include editorial emotion and narrative annotations. Run `python3 scripts/check_story_examples.py --tests` to validate structure, compare prose with the hashes stored in the script, verify lossless serialization, and run the test suite. Add `--show` to inspect the ranges. See [source credits and rights](examples/README.md).

## Specification

The [language specification](spec/spec.md) is written in English Markdown and defines names, syntax, content models, parsing, diagnostics, and lossless output. The [implementation](src/etml/) and [tests](tests/) accompany it.

## License and attribution

The project's code, documentation, and project-authored ETML markup are available under the [MIT License](LICENSE).

The underlying public-domain story texts retain their existing status. See [example attribution and rights information](examples/README.md) for authors, sources, production credits, and territorial scope.

<sub>An independent, unofficial project inspired by <em>Harmony</em>.</sub>
