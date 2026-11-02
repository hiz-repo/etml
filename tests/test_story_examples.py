"""Regression checks for editorial story annotations and their runnable checker."""

from hashlib import sha256
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('story_checks', ROOT / 'scripts/check_story_examples.py')
checks = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checks)

DECLARATION = '<?Emotion-in-Text Markup Language:version=1.2:encoding=EMO-590378?>'
DOCTYPE = '<!DOCTYPE etml PUBLIC :-//WENC/DTD ETML 1.2 transitional//EN>'


class StoryExampleTests(unittest.TestCase):
    def test_annotated_stories_preserve_supplied_prose(self):
        for name, digest in checks.TEXT_SHA256.items():
            with self.subTest(name=name):
                work, annotations = checks.check_file(ROOT / 'examples' / name, digest)
                self.assertTrue(annotations)
                self.assertEqual(len(work.units), 1)
                self.assertTrue(all(n.span.start < n.span.end for n in annotations))

    def test_negated_emotion_names_do_not_assert_jims_emotions(self):
        path = ROOT / 'examples/the_gift_of_the_magi.etml'
        work, annotations = checks.check_file(path, checks.TEXT_SHA256[path.name])
        sentence = ('It was not anger, nor surprise, nor disapproval, nor horror, '
                    'nor any of the sentiments that she had been prepared for.').encode()
        start = work.source.data.index(sentence)
        end = start + len(sentence)
        for n in annotations:
            if n.name in {'anger', 'surprise', 'horror'}:
                self.assertFalse(n.span.start < end and n.span.end > start)

    def test_checker_detects_text_change_and_missing_annotations(self):
        def document(body):
            return (DECLARATION + DOCTYPE + '<etml:lang=en><body>' + body
                    + '</body></etml>').encode()
        digest = sha256(b'Keep this text.').hexdigest()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'sample.etml'
            path.write_bytes(document('<surprise>Keep this text.</surprise>'))
            checks.check_file(path, digest)
            path.write_bytes(document('<surprise>Changed text.</surprise>'))
            with self.assertRaisesRegex(checks.CheckError, 'narrative text differs'):
                checks.check_file(path, digest)
            path.write_bytes(document('Keep this text.'))
            with self.assertRaisesRegex(checks.CheckError, 'no ETML annotations'):
                checks.check_file(path, digest)

    def test_script_runs_from_another_directory_and_shows_ranges(self):
        env = os.environ.copy()
        env.pop('PYTHONPATH', None)
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run(
                [sys.executable, str(ROOT / 'scripts/check_story_examples.py'), '--show'],
                cwd=directory, env=env, capture_output=True, text=True, check=False,
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.count('PASS '), 2)
        self.assertIn('<surprise>', result.stdout)
        self.assertIn('<confession>', result.stdout)
        self.assertEqual(result.stderr, '')


if __name__ == '__main__':
    unittest.main()
