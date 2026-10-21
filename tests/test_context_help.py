"""Help content stays concise and explicit, without importing GTK or optional ML libraries."""
import ast
from pathlib import Path
import unittest
from overmind.help_content import TOPICS, SHORT_HELP, tooltip_text


class ContextHelpTests(unittest.TestCase):
    def test_readable_focused_catalog(self):
        self.assertFalse(set(TOPICS) & set(SHORT_HELP))
        for key in TOPICS.keys() | SHORT_HELP.keys():
            with self.subTest(key=key):
                text=tooltip_text(key)
                self.assertTrue(text.strip())
                self.assertLessEqual(len(text),120)
                self.assertNotIn('\n',text)
        for key,topic in TOPICS.items():
            with self.subTest(topic=key):
                self.assertTrue(topic.title.strip())
                self.assertGreaterEqual(len(topic.paragraphs),2)
                self.assertLessEqual(len(topic.paragraphs),5)
                self.assertLessEqual(sum(len(p.split()) for p in topic.paragraphs),115)
                self.assertTrue(all(p.strip() for p in topic.paragraphs))

    def test_explicit_desktop_help_ids_exist(self):
        source=Path(__file__).resolve().parents[1]/'overmind'/'desktop.py'
        for node in ast.walk(ast.parse(source.read_text())):
            if not isinstance(node,ast.Call) or not isinstance(node.func,ast.Name):continue
            keys=[]
            if node.func.id in ('short_help','contextual','with_help','help_label') and len(node.args)>1:keys.append(node.args[1])
            keys.extend(k.value for k in node.keywords if k.arg in ('help_key','tip_key'))
            for key in keys:
                if isinstance(key,ast.Constant) and isinstance(key.value,str):
                    with self.subTest(line=node.lineno,key=key.value):self.assertTrue(tooltip_text(key.value))

    def test_unknown_topic_is_an_error(self):
        with self.assertRaises(KeyError):tooltip_text('unknown.setting')
