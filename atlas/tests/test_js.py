import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from atlas.extractors import js  # noqa: E402

YML = """\
aliases:
    oro/select2-share-component$: orosecuritypro/js/app/select2  # trailing
app-modules:
    - orotask/js/app/modules/template-macros-module
dynamic-imports:
    commons:
        - oro/sidebar/widget/assigned_tasks
        - oro/other
configs:
    orofusioncharts/js/extend/fusioncharts:
        licenseKey: abc==
map:
    '*':
        fusioncharts: orofusioncharts/js/extend/fusioncharts
shim:
    jquery:
        expose:
            - $,jQuery
"""

JS = """\
// mediator.trigger('commented:out')
mediator.trigger('widget_initialize', this);
mediator.execute(
    'showLoading'
);
mediator.setHandler('region:register', fn, this);
mediator.trigger('datagrid:beforeRemoveRow:' + this.name, model);
mediator.on('widget_initialize', cb);
/*
mediator.trigger('block:commented');
*/
mediator.trigger(`datagrid-${this.name}:rendered`, grid);
mediator.trigger(`${this.name}:lead`, grid);
mediator.trigger('after:block');
mediator.execute({name: 'layout:init', silent: true}, el);
mediator.trigger('dg:' + x);
mediator.trigger('widget_initialize:' + x);
"""


class Ctx:
    def __init__(self, root):
        self.root = root

    def rel(self, path):
        return os.path.relpath(os.path.realpath(path), os.path.realpath(self.root))


class JsTest(unittest.TestCase):
    def records(self):
        root = tempfile.mkdtemp()
        base = os.path.join(root, "vendor", "oro", "x", "Resources")
        os.makedirs(os.path.join(base, "config", "oro"))
        os.makedirs(os.path.join(base, "public", "js"))
        for name, body in (("config/oro/jsmodules.yml", YML), ("public/js/a.js", JS)):
            with open(os.path.join(base, name), "w") as fh:
                fh.write(body)
        return {r["id"]: r for r in js.extract(Ctx(root))}

    def test_yaml_sections(self):
        r = self.records()
        self.assertEqual(r["alias:oro/select2-share-component$"]["target"], "orosecuritypro/js/app/select2")
        self.assertEqual(r["alias:oro/select2-share-component$"]["line"], 2)
        self.assertEqual(r["app-module:orotask/js/app/modules/template-macros-module"]["line"], 4)
        self.assertEqual(r["dynamic-import:commons:oro/other"]["line"], 8)
        self.assertEqual(r["config:orofusioncharts/js/extend/fusioncharts"]["config_keys"], ["licenseKey"])
        self.assertEqual(r["map:*:fusioncharts"]["target"], "orofusioncharts/js/extend/fusioncharts")
        self.assertIn("shim:jquery", r)

    def test_mediator_events(self):
        r = self.records()
        self.assertNotIn("mediator:commented:out", r)
        ev = r["mediator:widget_initialize"]
        self.assertEqual(len(ev["triggers"]), 1)
        self.assertEqual(len(ev["listeners"]), 1)
        self.assertEqual(r["mediator:showLoading"]["line"], 3)
        self.assertEqual(r["mediator:region:register"]["handlers"][0].rsplit(":", 1)[1], "6")
        self.assertTrue(r["mediator:datagrid:beforeRemoveRow:*"]["dynamic"])

    def test_block_comment_and_template_names(self):
        r = self.records()
        self.assertNotIn("mediator:block:commented", r)
        self.assertEqual(r["mediator:after:block"]["line"], 14)
        self.assertTrue(r["mediator:datagrid-*"]["dynamic"])
        self.assertFalse(any("${" in k for k in r))

    def test_object_form_execute_is_a_trigger(self):
        r = self.records()
        self.assertEqual(r["mediator:layout:init"]["triggers"][0].rsplit(":", 1)[1], "15")

    def test_dynamic_prefix_marked_and_short_prefix_dropped(self):
        r = self.records()
        self.assertFalse(any(k.startswith("mediator:dg:") for k in r))
        dyn = r["mediator:widget_initialize:*"]
        self.assertEqual((dyn["keys"], dyn["dynamic"]), ([], True))
        self.assertIn("dynamic prefix", dyn["text"])
        # The literal event keeps its own record and exact key.
        self.assertEqual(r["mediator:widget_initialize"]["keys"], ["widget_initialize"])

    def test_yaml_comment_after_apostrophe_and_flow_list(self):
        tree, lines = js.parse_yaml("entry:\n    app: [a, 'b,c']  # don't\naliases:\n    x: y # it's\n")
        self.assertEqual(tree["entry"]["app"], ["a", "b,c"])
        self.assertEqual((tree["aliases"]["x"], lines[("aliases", "x")]), ("y", 4))

    def test_duplicate_ids_made_unique(self):
        ids = js._Ids()
        self.assertEqual([ids.unique("a"), ids.unique("a")], ["a", "a#2"])

    def test_parse_quoted_key_and_comment(self):
        tree, _ = js.parse_yaml("map:\n    '*':\n        a: b # c\n")
        self.assertEqual(tree, {"map": {"*": {"a": "b"}}})


if __name__ == "__main__":
    unittest.main()
