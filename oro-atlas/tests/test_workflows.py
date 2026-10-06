import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from atlas.extractors import load_all, operations, workflows  # noqa: E402

BUNDLE = os.path.join("src", "Acme", "Bundle", "FooBundle", "Resources", "config", "oro")

WORKFLOWS = """imports:
    - { resource: 'workflows/flow.yml' }
    - { workflow: flow, as: flow_copy, replace: [defaults.active] }
"""
FLOW = """imports:
    - { resource: 'flow/steps.yml' }
workflows:
    flow:
        entity: Acme\\Entity\\Thing   # trailing comment
        start_step: draft
        exclusive_active_groups: [grp_a, grp_b]
        transitions:
            go:
                step_to: done
                is_start: true
"""
STEPS = """workflows:
    flow:
        steps:
            draft:
                allowed_transitions:
                    - go
            done: ~
"""
ACTIONS = """operations:
    my_op:
        label: acme.op
        applications: [default]
        routes:
            - acme_route
        datagrids:
            - acme-grid
        preconditions:
            '@and':
                - '@not_blank': $.data
    DELETE:
        exclude_datagrids:
            - acme-grid
action_groups:
    my_group:
        parameters:
            thing: ~
        actions:
            - '@call_service_method': {service: x}
"""


class Ctx:
    def __init__(self, root):
        self.root = root

    def rel(self, path):
        return os.path.relpath(path, self.root)


def write(root, rel, text):
    path = os.path.join(root, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as fh:
        fh.write(text)


class ParseTest(unittest.TestCase):
    def test_block_scalar_and_comment_skipped(self):
        tree = workflows.parse("a:\n    b: |\n        c: not a key\n    d: 1 # note\n")
        a = tree.child("a")
        self.assertEqual(a.names(), ["b", "d"])
        self.assertEqual(workflows.scalar(a.child("d")), "1")

    def test_lists(self):
        tree = workflows.parse("a:\n    x: [p, 'q']\n    y:\n        - r\n    z:\n    - s\n    w: t\n")
        a = tree.child("a")
        self.assertEqual(workflows.as_list(a.child("x")), ["p", "q"])
        self.assertEqual(workflows.as_list(a.child("y")), ["r"])
        self.assertEqual(workflows.as_list(a.child("z")), ["s"])
        self.assertEqual(a.names(), ["x", "y", "z", "w"])


    def test_flow_list_keeps_quoted_comma(self):
        a = workflows.parse("a:\n    x: [p, 'q,r']\n").child("a")
        self.assertEqual(workflows.as_list(a.child("x")), ["p", "q,r"])


    def test_apostrophe_does_not_hide_comment(self):
        a = workflows.parse("a:\n    label: don't stop  # note: x\n    b: 1\n").child("a")
        self.assertEqual((workflows.scalar(a.child("label")), a.names()), ("don't stop", ["label", "b"]))

    def test_tilde_list_is_empty_and_acl_list_kept(self):
        a = workflows.parse("a:\n    routes: ~\n    acl_resource: [EDIT, $.data]\n").child("a")
        self.assertEqual(workflows.as_list(a.child("routes")), [])
        self.assertEqual(workflows.scalar(a.child("acl_resource")), "[EDIT, $.data]")


class LabelTest(unittest.TestCase):
    def test_label_from_default_translation_key(self):
        root = tempfile.mkdtemp()
        write(root, os.path.join(BUNDLE, "workflows.yml"),
              "imports:\n    - resource: 'workflows/a.yml'\n")
        write(root, os.path.join(BUNDLE, "workflows", "a.yml"), "workflows:\n    flow:\n        entity: E\n")
        write(root, os.path.join("src", "Acme", "Bundle", "FooBundle", "Resources", "translations", "workflows.en.yml"),
              "oro:\n    workflow:\n        flow:\n            label: 'Nice Flow'\n")
        rec = {r["id"]: r for r in workflows.extract(Ctx(root))}["flow"]
        self.assertEqual(rec["label_text"], "Nice Flow")
        self.assertIn('label="Nice Flow"', rec["text"])


class CloneOverrideTest(unittest.TestCase):
    def test_clone_with_own_definition_keeps_base_steps_and_transitions(self):
        root = tempfile.mkdtemp()
        write(root, os.path.join(BUNDLE, "workflows.yml"),
              "imports:\n    - { resource: 'workflows/a.yml' }\n    - { resource: 'workflows/b.yml' }\n")
        write(root, os.path.join(BUNDLE, "workflows", "a.yml"),
              "workflows:\n    base:\n        entity: E\n        steps:\n            s1:\n"
              "                allowed_transitions: [t1]\n            s2: ~\n"
              "        transitions:\n            t1:\n                step_to: s2\n")
        write(root, os.path.join(BUNDLE, "workflows", "b.yml"),
              "imports:\n    - { workflow: base, as: derived }\nworkflows:\n    derived:\n        steps:\n"
              "            s3: ~\n")
        recs = {r["id"]: r for r in workflows.extract(Ctx(root))}
        self.assertEqual(recs["derived"]["steps"], ["s1", "s2", "s3"])
        self.assertEqual([t["name"] for t in recs["derived"]["transitions"]], ["t1"])
        self.assertEqual(recs["derived"]["clone_of"], "base")


class ExtractTest(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        write(self.root, os.path.join(BUNDLE, "workflows.yml"), WORKFLOWS)
        write(self.root, os.path.join(BUNDLE, "workflows", "flow.yml"), FLOW)
        write(self.root, os.path.join(BUNDLE, "workflows", "flow", "steps.yml"), STEPS)
        write(self.root, os.path.join(BUNDLE, "actions.yml"), ACTIONS)
        self.ctx = Ctx(self.root)

    def test_workflow_merges_imports_and_clone(self):
        recs = {r["id"]: r for r in workflows.extract(self.ctx)}
        flow = recs["flow"]
        self.assertEqual(flow["entity"], "Acme\\Entity\\Thing")
        self.assertEqual(flow["steps"], ["draft", "done"])
        self.assertEqual(flow["exclusive_active_groups"], ["grp_a", "grp_b"])
        self.assertEqual(flow["transitions"], [{"name": "go", "from": ["draft"], "to": "done", "is_start": True}])
        self.assertTrue(flow["file"].endswith("workflows/flow.yml"))
        self.assertEqual(flow["line"], 4)
        self.assertEqual(len(flow["parts"]), 1)
        self.assertEqual(recs["flow_copy"]["clone_of"], "flow")
        self.assertEqual(recs["flow_copy"]["entity"], "Acme\\Entity\\Thing")

    def test_operations_and_action_groups(self):
        recs = {r["id"]: r for r in operations.extract(self.ctx)}
        op = recs["my_op"]
        self.assertEqual((op["kind"], op["routes"], op["datagrids"]), ("operation", ["acme_route"], ["acme-grid"]))
        self.assertEqual(op["line"], 2)
        self.assertEqual(recs["DELETE"]["exclude_datagrids"], ["acme-grid"])
        self.assertEqual(recs["my_group"]["kind"], "action_group")
        self.assertEqual(recs["my_group"]["parameters"], ["thing"])

    def test_both_shards_registered(self):
        mods = load_all()
        self.assertIn("workflows", mods)
        self.assertIn("operations", mods)


if __name__ == "__main__":
    unittest.main()
