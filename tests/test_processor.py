import contextlib
from dataclasses import FrozenInstanceError
import io
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

from etml import Limits, ParseError, parse
from etml.cli import main
from etml.validation import validate_semantics, validate_structure

DECL = '<?Emotion-in-Text Markup Language:version=1.2:encoding=EMO-590378?>'
DTD = '<!DOCTYPE etml PUBLIC :-//WENC/DTD ETML 1.2 transitional//EN>'
ROOT = Path(__file__).resolve().parents[1]


def document(content='', *, part='', lang='ja'):
    return (part + DECL + DTD + '<etml:lang=' + lang + '><body>' + content
            + '</body></etml>').encode('utf-8')


def named(work, name):
    return [n for n in work.walk() if n.name == name]


class ParserTests(unittest.TestCase):
    def bad(self, data, code=None):
        if isinstance(data, str):
            data = document(data)
        with self.assertRaises(ParseError) as caught:
            parse(data)
        d = caught.exception.diagnostic
        if code:
            self.assertEqual(d.code, code)
        self.assertIsNotNone(d.byte_offset)
        if d.code != 'encoding':
            self.assertGreaterEqual(d.line, 1)
            self.assertGreaterEqual(d.column, 1)
        return d

    def test_plain_text_and_entities_are_literal(self):
        w = parse(document('前<anger>中 &amp; &lt; > 後</anger>末'))
        self.assertEqual(len(w.units), 1)
        self.assertEqual(named(w, 'anger')[0].children[0].text, '中 &amp; &lt; > 後')
        self.assertEqual(validate_structure(w), [])
        self.assertEqual(w.serialize(), document('前<anger>中 &amp; &lt; > 後</anger>末'))

    def test_notes_keeps_both_slots_and_colons(self):
        w = parse(document('前<notes: 時刻: 正午=昼>時計<anger>声</anger></notes>後'))
        note = named(w, 'notes')[0]
        self.assertEqual(note.header_text, ' 時刻: 正午=昼')
        self.assertEqual(note.children[0].text, '時計')
        self.assertEqual(note.children[1].name, 'anger')
        slots = list(w.text_slots())
        self.assertEqual([(s.kind, s.value) for s in slots], [
            ('text', '前'), ('header-text', ' 時刻: 正午=昼'), ('text', '時計'),
            ('text', '声'), ('text', '後')])
        self.assertEqual(w.source.data[note.header_text_span.start:note.header_text_span.end],
                         note.header_text.encode())

    def test_multiple_units_interstitial_nulls_and_gaps(self):
        part = '<part:number=01:title=Me, I\'m Here/>'
        data = b'<!--- <ignored> -->\r\n' + document('甲', part=part)
        data += '\n<null>間<!-- note --></null>\r<null></null>\n'.encode() + document('乙')
        w = parse(data)
        self.assertEqual(len(w.units), 2)
        self.assertEqual(w.units[0].part.attributes, {'number': '01', 'title': "Me, I'm Here"})
        self.assertIsNone(w.units[1].part)
        self.assertEqual(len(named(w, 'null')), 2)
        self.assertEqual(w.serialize(), data)
        d = w.to_dict()
        self.assertEqual(d['children'][d['units'][0]['root']]['name'], 'etml')
        self.assertEqual(d['children'][d['units'][0]['part']]['kind'], 'part')

    def test_header_parts_values_and_duplicate_resource_ids(self):
        w = parse(document('<log:phonelink:id=same:playtime:2m52s06ms>記録</log>'
                           '<movie:ar:id=same></movie><movie:ar:id=same></movie>'))
        log = named(w, 'log')[0]
        self.assertEqual([(p.kind, p.name, p.value) for p in log.header], [
            ('modifier', 'phonelink', None), ('attribute', 'id', 'same'),
            ('marker', 'playtime', None), ('value', None, '2m52s06ms')])
        for p in log.header:
            if p.value_span:
                self.assertEqual(w.source.data[p.value_span.start:p.value_span.end].decode(), p.value)
        self.assertEqual(len(named(w, 'movie')), 2)

    def test_quoted_values_are_literal_and_values_can_end_in_slash(self):
        w = parse(document('<movie:ar:id=path/>文</movie>',
                           part='<part:number=epilogue:title="Place/"/>', lang='ja-JP'))
        self.assertEqual(named(w, 'movie')[0].attributes['id'], 'path/')
        self.assertEqual(w.units[0].part.attributes['title'], '"Place/"')
        self.assertEqual(w.units[0].root.attributes['lang'], 'ja-JP')

    def test_anonymous_multiline_and_ascii_payloads(self):
        w = parse(document('<declaration:anger><あ\nあ>< ascii ></declaration>'
                           '<music:name=Tune:id=m>< 旋律 ><123></music>'))
        self.assertEqual([n.payload for n in w.walk() if n.kind == 'anonymous'],
                         ['あ\nあ', ' ascii ', ' 旋律 ', '123'])

    def test_slash_in_atom_is_payload_not_self_closing(self):
        w = parse(document('<list><i: path/></list>'))
        self.assertEqual(named(w, 'i')[0].payload, ' path/')
        self.assertEqual(named(w, 'i')[0].kind, 'atom')

    def test_whitespace_is_exactly_four_characters(self):
        w = parse(document('<list><i:\u00a0></list>'))
        self.assertEqual(named(w, 'i')[0].payload, '\u00a0')
        self.bad(b'\xc2\xa0' + document(), 'structure')
        self.bad('<list>\u00a0<i: 値></list>', 'structure')
        self.bad('<list><i: \t\r\n></list>', 'payload')

    def test_comments_are_preserved_and_do_not_affect_models(self):
        data = document('<question><!-- <fake> --><q: 問><!---答---><a: 答></question>')
        w = parse(data)
        comments = [n for n in w.walk() if n.kind == 'comment']
        self.assertEqual([n.text for n in comments], [' <fake> ', '-答-'])
        self.assertEqual(w.serialize(), data)
        self.assertNotIn('comment', [s.kind for s in w.text_slots()])

    def test_comment_terminator_cannot_overlap_its_opener(self):
        self.bad(b'<!--->' + document(), 'unclosed')
        self.bad(b'<?>' + document(), 'syntax')
        self.bad(b'<?>', 'unclosed')
        for comment in (b'<!---->', b'<!-- --->', b'<!--<!-- nested text -->'):
            with self.subTest(comment=comment):
                data = comment + document()
                self.assertEqual(parse(data).serialize(), data)

    def test_every_token_and_node_has_exact_source_ranges(self):
        data = b'\xef\xbb\xbf' + document('<notes: 補足>😀e\u0301</notes>\r\n',
                                           part='<part:number=01:title=広場/>')
        w = parse(data)
        offset = 3
        for t in w.tokens:
            self.assertEqual(t.span.start, offset)
            self.assertEqual(data[t.span.start:t.span.end], t.raw.encode())
            offset = t.span.end
        self.assertEqual(offset, len(data))
        for n in w.walk():
            if n.kind == 'element':
                self.assertEqual(data[n.opening_span.start:n.opening_span.end][:1], b'<')
                self.assertEqual(data[n.closing_span.start:n.closing_span.end],
                                 ('</' + n.name + '>').encode())
            if n.payload_span and n.payload is not None:
                self.assertEqual(data[n.payload_span.start:n.payload_span.end], n.payload.encode())
        self.assertEqual(w.serialize(), data)
        with self.assertRaises(FrozenInstanceError):
            w.units[0].root.name = 'other'

    def test_unicode_columns_crlf_cr_lf_tabs_and_bom(self):
        prefix = '\ufeff' + DECL + '\r\n' + DTD + '\r<etml:lang=ja>\n<body>\r\n😀e\u0301\t'
        d = self.bad((prefix + '<unknown></body></etml>').encode(), 'name')
        self.assertEqual((d.line, d.column, d.byte_offset), (5, 5, len(prefix.encode())))
        for newline in ('\r\n', '\n', '\r'):
            data = ('\ufeff' + DECL + newline + DTD + newline +
                    '<etml:lang=ja><body>\ufeff</body></etml>').encode()
            w = parse(data)
            self.assertEqual(w.units[0].root.span.line, 3)
            self.assertEqual(w.units[0].declaration.span.column, 1)
            self.assertEqual(w.serialize(), data)
            self.assertIn('\ufeff', [slot.value for slot in w.text_slots()])

    def test_invalid_utf8_and_control_characters(self):
        for bad in (b'\xff', b'\xc0\xaf', b'\xed\xa0\x80'):
            with self.subTest(bad=bad):
                self.bad(bad, 'encoding')
        for value in set(range(32)) - {9, 10, 13}:
            with self.subTest(value=value):
                d = self.bad(document('甲' + chr(value)), 'encoding')
                self.assertEqual(d.byte_offset, len((DECL + DTD + '<etml:lang=ja><body>甲').encode()))

    def test_limits_are_reported_separately_and_configurable(self):
        data = document('本文')
        w = parse(data)
        count = len(list(w.walk()))
        self.assertEqual(parse(data, limits=Limits(len(data), 2, count)).serialize(), data)
        for limits in (Limits(len(data)-1, 2, count), Limits(len(data), 1, count),
                       Limits(len(data), 2, count-1)):
            with self.subTest(limits=limits), self.assertRaises(ParseError) as caught:
                parse(data, limits=limits)
            self.assertEqual(caught.exception.diagnostic.code, 'limit')
        for value in (0, -1, True, 1.2):
            with self.subTest(value=value), self.assertRaises(ValueError):
                Limits(max_depth=value)

    def test_depth_limit_and_json_at_default_boundary(self):
        data = document('<anger>' * 254 + '深' + '</anger>' * 254)
        w = parse(data)
        self.assertEqual(w.serialize(), data)
        self.assertTrue(json.dumps(w.to_dict(), ensure_ascii=False))
        with self.assertRaises(ParseError) as caught:
            parse(document('<anger>' * 255 + '</anger>' * 255))
        self.assertEqual(caught.exception.diagnostic.code, 'limit')

    def test_payload_empty_but_scalar_and_mixed_can_be_empty(self):
        parse(document('<anger></anger><notes: 注></notes>'
                       '<dictionary><item></item><description></description></dictionary>'))
        for bad in ('<list><i:></list>', '<notes: >文</notes>',
                    '<music:name=T:id=m><></music>'):
            with self.subTest(bad=bad):
                self.bad(bad, 'payload')

    def test_bad_names_and_no_anonymous_fallback(self):
        for bad in ('<unknown>文</unknown>', '<Anger>文</Anger>',
                    '<music:name=T:id=m><melody></music>'):
            with self.subTest(bad=bad):
                self.bad(bad, 'name')
        self.bad('<declaration><anger></anger></declaration>', 'structure')
        self.bad('<旋律>', 'structure')

    def test_bad_headers(self):
        for bad in ('<movie:id=x:ar></movie>', '<movie:ar:id=></movie>',
                    '<movie:ar:id= x></movie>', '<movie:ar:id=x ></movie>',
                    '<movie:ar:id=x\ny></movie>', '<movie:ar:id=x=y></movie>',
                    '<movie:ar:id=x:id=y></movie>', '<anger:unknown></anger>',
                    '<notes>本文</notes>', '<log:phonelink:id=x:playtime=2s></log>',
                    '<list:unknown><i: 文></list>', '<limit:patiance></limit>'):
            with self.subTest(bad=bad):
                self.bad(bad, 'header')

    def test_bad_end_tags_and_self_closing_forms(self):
        self.bad('<anger><surprise>文</anger></surprise>', 'end-tag')
        self.bad('</anger>', 'end-tag')
        for bad in ('<anger/>', '<anger></anger >', '<list><i: 値></list:item>',
                    '<list><i: 値></i></list>'):
            with self.subTest(bad=bad):
                self.bad(bad, 'syntax')

    def test_unclosed_and_nested_delimiters(self):
        for data in (b'<!-- text', b'<?text', b'<!DOCTYPE x', b'<anger',
                     document().replace(b'</body></etml>', b'')):
            with self.subTest(data=data):
                self.bad(data, 'unclosed')
        for data in (b'<music:name=x:id=y\n< tune >', b'<?a <x> ?>',
                     b'<!DOCTYPE <x>', document('<list><i: a<b></list>')):
            with self.subTest(data=data):
                self.bad(data, 'syntax')

    def test_declarations_are_fixed_and_do_not_load_resources(self):
        for raw in ('<?xml version="1.0"?>', '<!DOCTYPE etml SYSTEM "file:///etc/passwd">',
                    '<!DOCTYPE etml [<!ENTITY x "a">]>', '<![CDATA[x]]>'):
            with self.subTest(raw=raw):
                # A nested < is a syntax failure before declaration matching.
                self.bad(raw.encode())
        self.bad((DECL.replace('1.2', '1.3') + DTD + '<etml:lang=ja><body></body></etml>').encode(),
                 'declaration')

    def test_work_order_and_required_body(self):
        unit = document()
        bad_inputs = [b'', b'<!-- note -->', b'<null></null>' + unit,
                      unit + b'<null></null>', unit + b'text' + unit,
                      (DTD + DECL + '<etml:lang=ja><body></body></etml>').encode(),
                      unit.replace(b'<body></body>', b''),
                      unit.replace(b'<body></body>', b'<body></body><body></body>'),
                      unit.replace(b'<body>', b'<body><part:number=1:title=x/>'),
                      ('<part:number=1:title=x/>' + '<null></null>').encode() + unit,
                      unit + b'<part:number=2:title=x/>']
        for data in bad_inputs:
            with self.subTest(data=data):
                self.bad(data, 'structure')

    def test_all_content_model_families(self):
        fragments = [
            '<list><i: 値></list>', '<list:item><i: 値></list>',
            '<list:dialogue><d: 声></list>', '<list:protocol><p: 手順></list>',
            '<list:company><c: 会社></list>', '<list:meal><m: 食事></list>',
            '<list:action><a: 行動></list>', '<declaration><i: 値></declaration>',
            '<declaration><宣言></declaration>', '<declaration:anger>< 宣言 ></declaration>',
            '<declaration:calculation><pls: 値></declaration>',
            '<theorem:number><i: 値></theorem>', '<landscape><i: 値></landscape>',
            '<commonsense><i: 値><ex: 例></commonsense>', '<question><q: 問><a: 答></question>',
            '<definition><i: 朝><d: 説明><d: 補足><i: 夜><d: 説明></definition>',
            '<dictionary><item>甲</item><description>一</description>'
            '<item>乙</item><description>二</description></dictionary>',
            '<reference:textbook:id=t:line=01><content>引用</content></reference>',
            '<reference:thesis:id=t><title>題</title><author>甲</author><author>乙</author></reference>',
            '<movie:ar:id=m><silence><fear><horror>声</horror><limit:patience></limit>'
            '</fear></silence></movie>', '<music:name=T:id=m>< tune ></music>',
            '<log:media=Channel:id=l>記録</log>', '<log:phonelink:id=l>記録</log>',
            '<flashback:repeat><re: 記憶>間の本文<re: 記憶></flashback>',
            '<notes: 注>本文</notes>', '<relax><list><i: 値></list></relax>',
        ]
        for fragment in fragments:
            with self.subTest(fragment=fragment):
                w = parse(document(fragment))
                self.assertEqual(w.serialize(), document(fragment))
        w = parse(document(''.join(fragments)))
        self.assertEqual([n.name for n in named(w, 'definition')[0].children], ['i','d','d','i','d'])
        self.assertEqual(len(named(w, 'author')), 2)
        self.assertEqual(len(named(w, 'item')), 2)

    def test_structural_rejections(self):
        for bad in ('<list></list>', '<list><a: 値></list>', '<list>本文<i: 値></list>',
                    '<declaration><i: 値>< 宣言 ></declaration>',
                    '<commonsense><i: 値></commonsense>', '<question><a: 答><q: 問></question>',
                    '<definition><d: 説明><i: 値></definition>',
                    '<definition><i: 値></definition>', '<dictionary><item>甲</item></dictionary>',
                    '<reference:thesis:id=t><title>題</title></reference>',
                    '<reference:textbook:id=t:line=1><author>甲</author></reference>',
                    '<music:name=T:id=m>歌</music>', '<music:name=T:id=m><i: 歌></music>',
                    '<flashback:repeat>本文</flashback>', '<item>見出し</item>',
                    '<notes: 注><i: 値></notes>', '<anger><body></body></anger>',
                    '<dictionary><item><anger>甲</anger></item><description>乙</description></dictionary>'):
            with self.subTest(bad=bad):
                self.bad(bad, 'structure')

    def test_public_spec_examples_and_registered_names(self):
        spec = (ROOT / 'spec/spec.md').read_text()
        complete = re.findall(r'```etml\n(.*?)```', spec, re.S)[0]
        self.assertEqual(parse(complete.encode()).serialize(), complete.encode())
        table = spec.split('<a id="conformance-examples"></a>', 1)[1].split('<a id="index">', 1)[0]
        for fragment, result in re.findall(r'^\| `([^`]+)` \| ([^\n]+)', table, re.M):
            with self.subTest(fragment=fragment):
                if result.startswith('Invalid:'):
                    self.bad(fragment)
                else:
                    self.assertTrue(result.startswith('Valid:'), result)
                    parse(document(fragment))
        from etml.schema import NAMES, RANGES
        index = spec.split('<a id="index"></a>', 1)[1].split('<a id="references">', 1)[0]
        names = []
        for row in index.splitlines():
            if row.startswith('| ') and '[' in row:
                names.extend(re.findall(r'`([a-z]+)`', row.split('|')[2]))
        self.assertEqual(set(names), NAMES)
        self.assertEqual(len(names), 63)
        for name in RANGES:
            parse(document('<' + name + '><surprise>文</surprise></' + name + '>'))

    def test_all_public_examples(self):
        for path in sorted((ROOT / 'examples').glob('*.etml')):
            with self.subTest(path=path.name):
                data = path.read_bytes()
                self.assertEqual(parse(data).serialize(), data)

    def test_semantic_level_is_explicitly_unavailable(self):
        self.assertEqual(validate_semantics(parse(document()))[0].code, 'unavailable')


class CliTests(unittest.TestCase):
    def test_json_exit_codes_and_text_slots(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'input.etml'
            path.write_bytes(document('<notes: 注>本文</notes>'))
            for args, expected in ((['parse'], 0), (['text'], 0), (['validate'], 0),
                                   (['validate', '--level', 'semantic'], 3)):
                output = io.StringIO()
                argv = [args[0], str(path), *args[1:]]
                with contextlib.redirect_stdout(output):
                    self.assertEqual(main(argv), expected)
                payload = json.loads(output.getvalue())
                if args[0] == 'text':
                    self.assertEqual(payload['slots'][0]['kind'], 'header-text')
                if args[0] == 'validate':
                    self.assertEqual(payload['status'], 'unavailable' if expected == 3 else 'valid')
            path.write_bytes(document('<list></list>'))
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(main(['validate', str(path)]), 1)
            self.assertEqual(json.loads(output.getvalue())['status'], 'invalid')
            error = io.StringIO()
            with contextlib.redirect_stderr(error):
                self.assertEqual(main(['parse', str(path)]), 1)
            self.assertEqual(json.loads(error.getvalue())['code'], 'structure')
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(main(['parse', str(path.with_name('missing'))]), 2)

    def test_roundtrip_file_and_binary_stdout(self):
        with tempfile.TemporaryDirectory() as directory:
            source, target = Path(directory) / 'in.etml', Path(directory) / 'out.etml'
            data = b'\xef\xbb\xbf' + document('<notes: 注>本文\r\n</notes>')
            source.write_bytes(data)
            self.assertEqual(main(['roundtrip', str(source), '-o', str(target)]), 0)
            self.assertEqual(target.read_bytes(), data)
            result = subprocess.run([sys.executable, '-m', 'etml', 'roundtrip', str(source)],
                                    capture_output=True, check=False)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, data)
            self.assertEqual(result.stderr, b'')


if __name__ == '__main__':
    unittest.main()
