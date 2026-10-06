import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from atlas.extractors import mq  # noqa: E402

TOPIC = """<?php
namespace Acme\\Async\\Topic;
class FooTopic extends BaseTopic
{
    public const string NAME = 'acme.foo';
    public static function getName(): string { return self::NAME; }
    public static function getDescription(): string { return 'Does foo'; }
}
"""
BASE = """<?php
namespace Acme\\Async\\Topic;
abstract class BaseTopic { public static function getName(): string { return 'acme.base'; } }
"""
CHILD = """<?php
namespace Acme\\Async\\Topic;
class ChildTopic extends BaseTopic {}
"""
PROC = """<?php
namespace Acme\\Async;
use Acme\\Async\\Topic\\FooTopic;
use Acme\\Async\\Topic\\ChildTopic as Kid;
class P implements TopicSubscriberInterface
{
    public static function getSubscribedTopics()
    {
        return [FooTopic::getName(), Kid::getName(), 'literal.topic', Other::MISSING];
    }
}
"""
KEYED = """<?php
namespace Acme\\Async;
use Acme\\Async\\Topic\\FooTopic;
class K
{
    public static function getSubscribedTopics()
    {
        return [FooTopic::getName() => ['processorName' => 'x', 'queueName' => 'q']];
    }
}
"""

EDGE = """<?php
namespace Acme\\Async;
use Acme\\Async\\Topic\\FooTopic;
class E
{
    public static function getSubscribedTopics()
    {
        // 'commented.out' => FooTopic::getName()
        return [FooTopic::getName() => ['queueName' => Queues::Q, 'x' => Other::class]];
    }
}
"""


class FakeLocator:
    def __init__(self, files):
        self.files = files

    def file_of(self, fqcn):
        return self.files.get(fqcn)

    def locate(self, fqcn):
        return (self.files[fqcn], 3) if fqcn in self.files else (None, None)


class FakeCtx:
    def __init__(self, files, defs):
        self.locator = FakeLocator(files)
        self._defs = defs

    def container(self):
        return {"definitions": self._defs}


def build():
    d = tempfile.mkdtemp()
    files = {}
    for fqcn, src in {
        "Acme\\Async\\Topic\\FooTopic": TOPIC, "Acme\\Async\\Topic\\BaseTopic": BASE,
        "Acme\\Async\\Topic\\ChildTopic": CHILD, "Acme\\Async\\P": PROC, "Acme\\Async\\K": KEYED, "Acme\\Async\\E": EDGE,
    }.items():
        path = os.path.join(d, fqcn.replace("\\", "_") + ".php")
        with open(path, "w") as fh:
            fh.write(src)
        files[fqcn] = path
    defs = {
        "foo": {"class": "Acme\\Async\\Topic\\FooTopic", "tags": [{"name": mq.TOPIC_TAG}]},
        "child": {"class": "Acme\\Async\\Topic\\ChildTopic", "tags": [{"name": mq.TOPIC_TAG}]},
        "p": {"class": "Acme\\Async\\P", "tags": [{"name": mq.PROCESSOR_TAG}]},
        "k": {"class": "Acme\\Async\\K", "tags": [{"name": mq.PROCESSOR_TAG, "parameters": {"topicName": "acme.tag"}}]},
        "e": {"class": "Acme\\Async\\E", "tags": [{"name": mq.PROCESSOR_TAG}]},
        "other": {"class": "Acme\\Async\\P", "tags": [{"name": "kernel.event_listener"}]},
    }
    return {r["id"]: r for r in mq.extract(FakeCtx(files, defs))}


class MqTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.recs = build()

    def test_topic_name_from_self_const_and_description(self):
        t = self.recs["acme.foo"]
        self.assertEqual((t["kind"], t["description"]), ("topic", "Does foo"))

    def test_topic_name_inherited_from_parent(self):
        self.assertEqual(self.recs["acme.base"]["class"], "Acme\\Async\\Topic\\ChildTopic")

    def test_processor_topics_aliased_import_literal_and_unresolved(self):
        p = self.recs["p"]
        self.assertEqual(p["topics"], ["acme.base", "acme.foo", "literal.topic"])
        self.assertEqual(len(p["unresolved_topics"]), 1)

    def test_keyed_form_ignores_option_strings_and_tag_param_added(self):
        self.assertEqual(self.recs["k"]["topics"], ["acme.foo", "acme.tag"])

    def test_option_refs_comments_and_class_constant_are_not_topics(self):
        e = self.recs["e"]
        self.assertEqual((e["topics"], e["unresolved_topics"]), (["acme.foo"], []))

    def test_topic_links_processors(self):
        self.assertEqual([x["service"] for x in self.recs["acme.foo"]["processors"]], ["e", "k", "p"])

    def test_snake_case_query_matches_camel_case_class(self):
        from atlas import cli
        hits, _ = cli.search_records(list(self.recs.values()), "foo_topic", 5)
        self.assertEqual([h["id"] for h in hits], ["acme.foo"])
        self.assertEqual(mq.snake_keys("A\\CPLRebuildTopic", "a.b"), ["a_b", "cpl_rebuild_topic"])

    def test_unreadable_class_file_is_skipped(self):
        class Loc:
            def file_of(self, fqcn):
                return tempfile.mkdtemp()  # a directory: open() fails

        class C:
            locator = Loc()
        self.assertIsNone(mq.Resolver(C()).parse("X"))

    def test_untagged_service_ignored(self):
        self.assertNotIn("other", self.recs)


if __name__ == "__main__":
    unittest.main()
