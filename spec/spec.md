# ETML Language Specification

ETML (Emotion-in-Text Markup Language) combines literary text with named ranges, lists, definitions, references, and document boundaries. This specification defines its syntax, document model, parsing rules, diagnostics, and lossless serialization.

## Contents

1. [Introduction](#introduction)
2. [Common infrastructure](#infrastructure)
3. [Documents and data model](#documents)
4. [Elements and items](#elements)
5. [Syntax](#syntax)
6. [Parsing](#parsing)
7. [Serialization and text access](#serialization)
8. [Conformance and diagnostics](#conformance)
9. [Index](#index)
10. [References](#references)

<a id="introduction"></a>

## 1. Introduction

This section and all examples are informative. The remaining requirements are normative.

### 1.1 Notation overview

A start tag contains a base name followed by colon-separated modifiers or attributes. Its end tag contains the base name. Standalone items and anonymous text contain their payload inside a single pair of angle brackets.

| Form | Purpose |
| --- | --- |
| `<anger>text</anger>` | Named text range |
| `<list:item>…</list>` | Element with a modifier |
| `<movie:ar:id=clip-01>…</movie>` | Element with a modifier and an attribute |
| `<i: A key>` | Standalone item |
| `< melody >` | Anonymous text |
| `<notes: An old name>North Square</notes>` | Element with header text and child content |
| `<part:number=01:title=Station/>` | Chapter marker |

### 1.2 Example

A work containing one document unit:

```etml
<part:number=01:title=Station/>
<?Emotion-in-Text Markup Language:version=1.2:encoding=EMO-590378?>
<!DOCTYPE etml PUBLIC :-//WENC/DTD ETML 1.2 transitional//EN>
<etml:lang=en>
<body>
The station clock rang. <surprise>I looked up.</surprise>
<list:item>
    <i: A key>
    <i: A notebook>
</list>
<notes: An old name>North Square</notes> was our meeting place.
</body>
</etml>
```

<a id="infrastructure"></a>

## 2. Common infrastructure

### 2.1 Requirements and conformance classes

**MUST** and **MUST NOT** express requirements. **MAY** expresses permission.

- A **conforming work** satisfies Sections 2–6.
- A **conforming reader** preserves the information in Section 3 and follows Section 6 within its published processing limits. Limit failures follow Section 8.
- A **conforming lossless serializer** also satisfies Section 7.1.

### 2.2 Terminology

| Term | Definition |
| --- | --- |
| Work | The complete input, containing one or more document units and their separators |
| Document unit | An optional chapter marker followed by a declaration, a DOCTYPE, and an `etml` element |
| Paired element | A structure delimited by a start tag and an end tag |
| Base name | The name preceding the first colon in a start tag, or the entire name when no colon occurs |
| Header | The name and following components inside a start tag |
| Modifier | A header component such as `item` or `ar` |
| Attribute | A key–value component such as `id=clip-01` |
| Standalone item | A named payload written as `<i: text>` |
| Anonymous text | An unnamed payload enclosed in angle brackets |
| Ordinary text | Characters outside markup |
| Header text | The payload between the first colon and `>` in a `notes` start tag |

### 2.3 Characters, names, and whitespace

Input **MUST** be valid UTF-8. An optional leading UTF-8 BOM **MUST** be retained for serialization. A subsequent U+FEFF is ordinary text.

Permitted characters are U+0009 (TAB), U+000A (LF), U+000D (CR), and Unicode scalar values from U+0020 upwards. All other characters are invalid.

**Whitespace** consists of TAB, LF, CR, and U+0020 (SPACE). LF, CRLF, and standalone CR are permitted line endings. Readers **MUST** preserve whitespace, line endings, and Unicode sequences exactly.

Tag names, attribute names, and modifiers **MUST** match their registered spellings and case.

### 2.4 Values and payloads

`V` and `P` are grammar symbols:

| Symbol | Definition |
| --- | --- |
| `V` | A nonempty, single-line string containing none of TAB, LF, CR, `:`, `<`, `>`, or `=`, with no leading or trailing SPACE |
| `P` | Text containing no `<` or `>` and at least one non-whitespace character; line breaks, colons, and equals signs are permitted |

Interior spaces and punctuation are literal characters in `V`. Quotation marks are literal: the value of `title="Station"` includes both quotation marks.

Readers **MUST** preserve values as strings, including leading zeros and all permitted whitespace. Unless a field states otherwise, any `V` is permitted. IDs **MAY** repeat within a work.

<a id="documents"></a>

## 3. Documents and data model

### 3.1 Work structure

A work **MUST** match this grammar. `?` means zero or one occurrence, and `*` means zero or more. `Gap` is any sequence of whitespace and comments, including an empty sequence.

```text
Work = BOM? Gap Unit (Gap (Null Gap)* Unit)* Gap
Unit = (Part Gap)? Declaration Gap Doctype Gap Etml
```

`Part`, `Etml`, and `Null` are defined in Section 4.1. `Declaration` and `Doctype` are defined in Section 5.1.

A work contains at least one unit. A `null` element occurs only between units; consecutive `null` elements are permitted. Each chapter marker belongs to the following unit. Chapter numbers and titles **MAY** repeat, and chapter numbers need not form a sequence.

Each unit contains its own declaration and DOCTYPE. Ordinary text outside elements is restricted to whitespace. Inter-unit whitespace and comments **MUST** remain in source order.

### 3.2 Required information

A reader **MUST** expose the following information:

| Structure | Required information |
| --- | --- |
| Work and document unit | Source order, optional chapter marker, and associations between the declaration, DOCTYPE, and root element |
| Paired element | Base name, ordered header components, ordered content, and start/end positions |
| Standalone item | Name, complete `P`, and position |
| Anonymous text | Complete `P` and position |
| `notes` | Header `P` and child content as separate text locations |
| Ordinary text and comment | Original characters and position |
| `part` | `number`, `title`, and position |

Header components **MUST** retain their order and distinguish modifiers, attributes, and the `playtime` marker with its following value. Repeated children, including authors and dictionary entries, **MUST** remain separate and ordered.

Original delimiters, whitespace, BOM, and value spellings **MUST** be recoverable from the retained source and ranges, or an equivalent representation.

### 3.3 Content models

Each element specifies the types and order of its direct children. Whitespace and comments ignored during validation **MUST** remain in the data model.

- **T**: Any sequence of ordinary text and comments, including an empty sequence.
- **M**: Any sequence of ordinary text, comments, and the 44 paired elements defined in Sections 4.2–4.6, including an empty sequence.
- **Item sequence**: The child sequence specified in an element's table. Whitespace and comments are permitted before, between, and after children. Other ordinary text is invalid.

In item sequences, `+` means one or more occurrences, `*` means zero or more, `|` means a choice, and parentheses group terms. `Anon` denotes anonymous text.

Readers **MUST** validate each element's own content model. Tag nesting determines containment; indentation is preserved as text.

<a id="elements"></a>

## 4. Elements and items

Only the forms listed in this section are permitted. Paired elements use `</base-name>` end tags. Header components **MUST** occur in the listed order and multiplicity. `V` and `P` follow Section 2.4.

<a id="document-elements"></a>

### 4.1 Document structure

| Name | Form | Context | Content and role |
| --- | --- | --- | --- |
| `part` | `<part:number=V:title=V/>` | Before a unit's declaration | Chapter number and title; self-contained |
| `etml` | `<etml:lang=V>` | After a unit's declaration and DOCTYPE | Exactly one `body`, surrounded by optional whitespace and comments |
| `body` | `<body>` | Direct child of `etml` | M; document text |
| `null` | `<null>` | Between document units | T; inter-document text separator |

The `lang` attribute is an opaque language identifier preserved exactly. A `null` element retains its text content.

<a id="range-elements"></a>

### 4.2 Unmodified range elements

The following 29 elements use `<name>…</name>`, have no header components, occur wherever M is permitted, and contain M. Each preserves its distinct name and enclosed range.

```text
anger          antipathy       boredom         cautiously
confession     confusion       disappointment  disturbed
fear           hopelessness    horror          laugh
maxim          mourn           panic           passion
recollection   regret          relax           remind
ridicule       scorn           sentiment       shake
shout          silence         surprise        tension
uncomfortable
```

<a id="structured-elements"></a>

### 4.3 Lists and structured content

These eight elements occur wherever M is permitted. Their content is an item sequence.

| Header | Content model | Role |
| --- | --- | --- |
| `list` / `list:item` | `i+` | Item list; retain the chosen header form |
| `list:dialogue` | `d+` | Dialogue items |
| `list:protocol` | `p+` | Procedure items |
| `list:company` | `c+` | Company items |
| `list:meal` | `m+` | Meal items |
| `list:action` | `a+` | Action items |
| `declaration` | `i+` or `Anon+` | Declaration using one item type |
| `declaration:calculation` | `pls+` | Calculation declaration |
| `declaration:anger` | `Anon+` | Declaration with anonymous text |
| `theorem:number` | `i+` | Theorem items |
| `landscape` | `i+` | Landscape items |
| `commonsense` | `i+ ex` | Items followed by one `ex` item |
| `question` | `q a` | One question and one answer |
| `definition` | `(i d+)+` | Items followed by descriptions |
| `dictionary` | `(item description)+` | Term–description pairs |

A `definition` **MUST** retain a flat child sequence. Item counts have no language-defined maximum.

<a id="reference-elements"></a>

### 4.4 References and media

These four elements occur wherever M is permitted.

| Header | Content model | Retained information |
| --- | --- | --- |
| `reference:textbook:id=V:line=V` | Item sequence `content` | Reference ID, line identifier, and one content element |
| `reference:thesis:id=V` | Item sequence `title author+` | One title and one or more authors |
| `movie:ar:id=V` | M | Modifier, reference ID, and content |
| `log:phonelink:id=V` | M | Modifier, ID, and content |
| `log:phonelink:id=V:playtime:V` | M | Modifier, ID, `playtime` marker, following value, and content |
| `log:media=V:id=V` | M | Media identifier, ID, and content |
| `music:name=V:id=V` | Item sequence `Anon+` | Name, ID, and anonymous text items |

The `line` and `playtime` values remain strings. Readers **MUST** preserve the colon-separated `playtime:V` form.

<a id="flashback-limit"></a>

### 4.5 `flashback` and `limit`

Both elements occur wherever M is permitted.

| Header | Content model |
| --- | --- |
| `flashback:repeat` | Any sequence of ordinary text, comments, and `re` items, containing at least one `re` |
| `limit:patience` | M |

<a id="notes-element"></a>

### 4.6 `notes`

`notes` uses `<notes:P>…</notes>`, occurs wherever M is permitted, and contains M.

Readers **MUST** retain everything after the first colon and before `>` as one header-text payload `P`, separate from child content.

<a id="text-elements"></a>

### 4.7 Text elements

These five elements have no header components and contain T. They occur only under the specified direct parent.

| Name | Direct parent | Role |
| --- | --- | --- |
| `item` | `dictionary` | Term |
| `description` | `dictionary` | Description of the preceding term |
| `content` | `reference:textbook` | Referenced content |
| `title` | `reference:thesis` | Reference title |
| `author` | `reference:thesis` | Author name |

<a id="atoms"></a>

### 4.8 Standalone items

A standalone item uses `<name:P>`. The complete payload, including surrounding whitespace, **MUST** be preserved. Each item is self-contained and accepts only the following direct parents.

| Name | Permitted parent headers |
| --- | --- |
| `i` | `list`, `list:item`, `declaration`, `theorem:number`, `landscape`, `definition`, `commonsense` |
| `d` | `list:dialogue`, `definition` |
| `p` | `list:protocol` |
| `re` | `flashback:repeat` |
| `a` | `question`, `list:action` |
| `m` | `list:meal` |
| `pls` | `declaration:calculation` |
| `c` | `list:company` |
| `q` | `question` |
| `ex` | `commonsense` |

<a id="anonymous"></a>

### 4.9 Anonymous text

Anonymous text uses `<P>` and occurs only as direct content of `declaration`, `declaration:anger`, or `music:name=V:id=V`.

The character immediately after `<` **MUST NOT** be an ASCII letter, `/`, `!`, or `?`. ASCII-letter payloads require leading whitespace, as in `< melody >`. Compact non-ASCII payloads such as `<旋律>` are permitted.

Once a sequence is recognized as named markup, an invalid name or context **MUST** produce an error. Readers **MUST NOT** reinterpret it as anonymous text.

<a id="syntax"></a>

## 5. Syntax

### 5.1 Declaration and DOCTYPE

Every document unit **MUST** contain these exact strings once each, in this order, including the displayed case and spacing. Gap is permitted around and between them.

```etml
<?Emotion-in-Text Markup Language:version=1.2:encoding=EMO-590378?>
<!DOCTYPE etml PUBLIC :-//WENC/DTD ETML 1.2 transitional//EN>
```

`version` and `encoding` are declaration metadata. UTF-8 decoding follows Section 2.3. Readers **MUST NOT** fetch external DTDs or expand entities.

### 5.2 Names and headers

A name candidate matches `[A-Za-z][A-Za-z0-9_-]*` and **MUST** be registered in Section 4. It **MUST** be followed immediately by `:`, `>`, or `/>`. Named markup contains no formatting whitespace around the name.

For ordinary headers, split components at colons and attribute keys from values at `=`. The result **MUST** match one listed header form exactly, including component order and count.

Identify standalone items and `notes` before splitting components. For these forms, the first colon introduces the complete `P`. For example, `<i: Time: noon>` contains the payload ` Time: noon`.

### 5.3 Start tags, end tags, and termination

Paired elements start with `<header>` and end with exactly `</base-name>`. Every start tag **MUST** have an explicitly nested matching end tag. Empty content, where permitted, uses both tags: `<anger></anger>`.

Only `part` uses `/>` as its terminator. Strip that terminator before reading its header. Elsewhere, `/` is a literal header or payload character: the payload in `<i: path/>` is ` path/`.

### 5.4 Ordinary text and special characters

Ordinary text consists of permitted characters other than `<`. A `<` always starts markup. A `>`, `&`, or quotation mark in ordinary text is literal.

Character references and escape sequences are treated literally. `&lt;` is the four-character string `&lt;`.

### 5.5 Comments

A comment starts with `<!--` and ends at the first subsequent `-->`. Its contents are literal permitted characters. An additional hyphen in `<!---` belongs to the comment content.

Comments are permitted in work-level Gap, around `body` inside `etml`, and in element content. They **MUST** be retained with their source positions and ignored when counting children for content-model validation. Header and payload syntax follows Sections 2.4 and 5.2.

<a id="parsing"></a>

## 6. Parsing

### 6.1 Token recognition

Record an optional leading BOM, then scan from the next character, using this precedence:

1. Collect consecutive characters other than `<` as ordinary text.
2. On `<!--`, read a comment through its terminator.
3. On `<?`, read through `?>` and require the declaration in Section 5.1.
4. On `<!`, read through `>` and require the DOCTYPE in Section 5.1.
5. On `</`, require an end tag naming a registered paired element.
6. On `<` followed by an ASCII letter, read and validate a name candidate. Apply the rules for a standalone item, `notes`, `part`, or another paired element.
7. Otherwise, read an anonymous-text candidate through the first `>` and validate its payload and context.

A new `<` before a non-comment token's terminator is a syntax error. End of input before a required terminator is an `unclosed` error. Names **MUST** be accepted or rejected by their exact registered spelling.

### 6.2 Tree construction and validation

1. Read the work structure in Section 3.1. Associate each chapter marker, declaration, and DOCTYPE with its document unit's `etml` root.
2. On a paired-element start tag, validate its header, append the element to the current content sequence, and push it onto the open-element stack.
3. Append ordinary text, comments, standalone items, and anonymous text directly to the current content sequence.
4. On an end tag, require its base name to match the stack's top element, then close and pop that element.
5. Validate each element's content model and direct parent. Ignore whitespace and comments only for the purpose of item-sequence validation.
6. At end of input, require an empty stack, complete document units, and a valid work structure.

Readers **MAY** validate content during or after tree construction. They **MAY** continue after a diagnostic and expose partial results. A failed parse **MUST** be reported as nonconforming.

### 6.3 Source positions

Every token and structure **MUST** expose a zero-based, half-open UTF-8 byte range `[start, end)`. An element's range extends from its start tag's `<` through the byte after its end tag's `>`. Every text-bearing token **MUST** also expose its content range, excluding delimiters.

Diagnostic lines and columns are one-based. Columns count Unicode scalar values, with TAB counting as one column. CRLF counts as one line break; standalone CR and LF each count as one. A leading BOM contributes to byte offsets and occupies zero columns.

<a id="serialization"></a>

## 7. Serialization and text access

### 7.1 Lossless serialization

Serializing an unedited conforming work **MUST** reproduce its original bytes exactly, including header order, whitespace, line endings, comments, BOM, and value spellings. The structured information required by Section 3 **MUST** remain accessible.

### 7.2 Text access

Readers **MUST** expose ordinary text, standalone-item payloads, anonymous-text payloads, and `notes` header text as distinct text locations. Accessed payloads exclude delimiters and preserve their own whitespace and line endings.

Presentation and flattened reading order are outside the scope of this specification.

<a id="conformance"></a>

## 8. Conformance and diagnostics

### 8.1 Requirements

A work is conforming only when all input, token, header, document-order, and content-model requirements are satisfied.

Readers **MUST** provide the following diagnostic categories and source positions. Message wording and diagnostic reporting order are implementation-defined.

| Category | Condition | Position |
| --- | --- | --- |
| `encoding` | Invalid UTF-8 or a prohibited character | Invalid byte position; line and column may be omitted if decoding fails |
| `declaration` | Unsupported declaration or DOCTYPE | Candidate's opening `<` |
| `name` | Unregistered or incorrectly cased name | Candidate's opening `<` |
| `syntax` | Invalid delimiter, character after a name, or end-tag form | Token's opening `<` |
| `header` | Invalid component, order, or `V` | Start tag's opening `<` |
| `payload` | Empty or whitespace-only `P` | Token's opening `<` |
| `unclosed` | Unterminated token or element | Unclosed opening `<` |
| `end-tag` | End tag with no matching open element | End tag's opening `<` |
| `structure` | Invalid parent, content model, document order, or missing required structure | Offending child's start or the start of a parent with missing content; end of input for a work-level omission detected there |
| `limit` | Published implementation limit reached | Input position at interruption |

Readers **MUST NOT** report corrected invalid input as conforming. Implementations **MUST** publish their processing limits and report limit failures separately from syntax errors. The language imposes no maximum element count, item count, or nesting depth.

<a id="conformance-examples"></a>

### 8.2 Examples

These fragments assume a valid enclosing document and parent.

| Input | Result |
| --- | --- |
| `<list:item><i: A key></list>` | Valid: list containing an item |
| `<definition><i: Morning><d: The start of the day></definition>` | Valid: `i d+` sequence |
| `<music:name=Tone:id=music-01>< melody ></music>` | Valid: anonymous text with leading whitespace |
| `<notes: Time: noon>Clock</notes>` | Valid: colon within header text |
| `<anger><surprise>A voice</anger></surprise>` | Invalid: mismatched end tag |
| `<list:item><i: A key></list:item>` | Invalid: modifier in an end tag |
| `<list:item><a: Walk></list>` | Invalid: item type rejected by its parent |
| `<notes>Clock</notes>` | Invalid: missing header-text syntax |
| `<music:name=Tone:id=music-01><melody></music>` | Invalid: unregistered name |
| `<movie:id=clip-01:ar>Footage</movie>` | Invalid: header component order |
| `<anger/>` | Invalid: paired element requires an end tag |

<a id="index"></a>

## 9. Index

The specification registers 63 names:

| Kind | Names | Definition |
| --- | --- | --- |
| Chapter marker: 1 | `part` | [4.1](#document-elements) |
| Document elements: 3 | `etml`, `body`, `null` | [4.1](#document-elements) |
| Unmodified range elements: 29 | `anger`, `antipathy`, `boredom`, `cautiously`, `confession`, `confusion`, `disappointment`, `disturbed`, `fear`, `hopelessness`, `horror`, `laugh`, `maxim`, `mourn`, `panic`, `passion`, `recollection`, `regret`, `relax`, `remind`, `ridicule`, `scorn`, `sentiment`, `shake`, `shout`, `silence`, `surprise`, `tension`, `uncomfortable` | [4.2](#range-elements) |
| Structured elements: 8 | `list`, `declaration`, `theorem`, `landscape`, `commonsense`, `question`, `definition`, `dictionary` | [4.3](#structured-elements) |
| Reference and media elements: 4 | `reference`, `movie`, `log`, `music` | [4.4](#reference-elements) |
| Other paired elements: 3 | `flashback`, `limit`, `notes` | [4.5](#flashback-limit), [4.6](#notes-element) |
| Text elements: 5 | `item`, `description`, `content`, `title`, `author` | [4.7](#text-elements) |
| Standalone items: 10 | `i`, `d`, `p`, `re`, `a`, `m`, `pls`, `c`, `q`, `ex` | [4.8](#atoms) |

Header attribute keys are `number`, `title`, `lang`, `id`, `line`, `media`, and `name`. Declaration metadata uses `version` and `encoding`. `playtime` is a marker followed by a positional value; `number` in `theorem:number` is a modifier.

<a id="references"></a>

## 10. References

Project Itoh. *Harmony*. Hayakawa Publishing, 2014.
