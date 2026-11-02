"""Closed vocabulary and header forms from docs/etml-spec/spec.md."""

DECLARATION = "<?Emotion-in-Text Markup Language:version=1.2:encoding=EMO-590378?>"
DOCTYPE = "<!DOCTYPE etml PUBLIC :-//WENC/DTD ETML 1.2 transitional//EN>"
RANGES = frozenset("""
anger antipathy boredom cautiously confession confusion disappointment disturbed
fear hopelessness horror laugh maxim mourn panic passion recollection regret relax
remind ridicule scorn sentiment shake shout silence surprise tension uncomfortable
""".split())
SCALARS = frozenset("item description content title author".split())
ATOMS = frozenset("i d p re a m pls c q ex".split())
MIXED = RANGES | frozenset("""
list declaration theorem landscape commonsense question definition dictionary
reference movie log music flashback limit notes
""".split())
PAIRED = MIXED | SCALARS | {"etml", "body", "null"}
NAMES = PAIRED | ATOMS | {"part"}

# @key: attribute, !word: marker, $: positional V; other words: modifiers.
HEADERS: dict[str, tuple[tuple[str, ...], ...]] = {
    name: ((),) for name in RANGES | SCALARS | {"body", "null"}
}
HEADERS.update({
    "part": (("@number", "@title"),), "etml": (("@lang",),),
    "list": ((), ("item",), ("dialogue",), ("protocol",), ("company",),
             ("meal",), ("action",)),
    "declaration": ((), ("calculation",), ("anger",)),
    "theorem": (("number",),), "landscape": ((),),
    "commonsense": ((),), "question": ((),),
    "definition": ((),), "dictionary": ((),),
    "reference": (("textbook", "@id", "@line"), ("thesis", "@id")),
    "movie": (("ar", "@id"),),
    "log": (("phonelink", "@id"), ("phonelink", "@id", "!playtime", "$"),
            ("@media", "@id")),
    "music": (("@name", "@id"),),
    "flashback": (("repeat",),), "limit": (("patience",),),
})
