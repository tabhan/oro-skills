import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from atlas.extractors import entity  # noqa: E402

ATTR = """<?php
namespace Acme\\Bundle\\FooBundle\\Entity;

use Acme\\Bundle\\FooBundle\\Entity\\Repository\\FooRepository;
use Doctrine\\ORM\\Mapping as ORM;
use Oro\\Bundle\\EntityConfigBundle\\Metadata\\Attribute\\Config;

#[ORM\\Entity(repositoryClass: FooRepository::class)]
#[ORM\\Table(name: 'acme_foo')]
#[Config(
    routeName: 'acme_foo_index',
    defaultValues: [
        'entity' => ['icon' => 'fa-x', 'contact' => ['email' => [['fieldName' => 'a']]]],
        'ownership' => ['owner_type' => 'USER'],
        'security' => ['type' => 'ACL'],
    ]
)]
class Foo
{
    public $x = ['entity' => 1];
}
"""

ANN = """<?php
namespace Acme\\Entity;
use Doctrine\\ORM\\Mapping as ORM;
/**
 * @ORM\\Entity(repositoryClass="Acme\\Entity\\BarRepo")
 * @ORM\\Table(name="acme_bar")
 */
class Bar {}
"""

EXTEND = """aaxis_entity_extend:
    Oro\\Bundle\\ProductBundle\\Entity\\Product:
        customRepositoryClassName: Buckman\\Repo\\ProductRepository
    Buckman\\Entity\\Pub:
        uniqueConstraints:
            u1:
                columns:
                    - a
"""

SCOPES = """entity_config:
    ai_agent:
        entity:
            items:
                inc:
                    options:
                        value_type: boolean
        field:
            items:
                inc2:
                    options: {}
"""


class ParsePhpTest(unittest.TestCase):
    def test_attribute_entity(self):
        e = entity.parse_php(ATTR)
        self.assertEqual(e["class"], "Acme\\Bundle\\FooBundle\\Entity\\Foo")
        self.assertEqual(e["table"], "acme_foo")
        self.assertEqual(e["repository"], "Acme\\Bundle\\FooBundle\\Entity\\Repository\\FooRepository")
        self.assertEqual(sorted(e["scopes"]), ["entity", "ownership", "security"])
        self.assertEqual(e["scopes"]["entity"], ["icon", "contact"])
        self.assertEqual(e["line"], 18)

    def test_annotation_entity(self):
        e = entity.parse_php(ANN)
        self.assertEqual((e["table"], e["repository"]), ("acme_bar", "Acme\\Entity\\BarRepo"))

    def test_non_entity_ignored(self):
        self.assertIsNone(entity.parse_php("<?php\nnamespace A;\nclass X {}\n"))

    def test_relative_repo_resolved_in_namespace(self):
        src = "<?php\nnamespace A\\E;\nuse Doctrine\\ORM\\Mapping as ORM;\n#[ORM\\Entity(repositoryClass: R\\Repo::class)]\nclass X {}\n"
        self.assertEqual(entity.parse_php(src)["repository"], "A\\E\\R\\Repo")


class ParseYamlTest(unittest.TestCase):
    def test_extend_overrides(self):
        got = entity.parse_extend_overrides(EXTEND)
        self.assertEqual(got[0], ("Oro\\Bundle\\ProductBundle\\Entity\\Product", "Buckman\\Repo\\ProductRepository", 2))
        self.assertEqual(got[1][:2], ("Buckman\\Entity\\Pub", None))

    def test_extend_override_comment_and_two_space_indent(self):
        got = entity.parse_extend_overrides("aaxis_entity_extend:\n  # why\n  A\\B:\n    customRepositoryClassName: 'R\\S' # x\n")
        self.assertEqual(got, [("A\\B", "R\\S", 3)])

    def test_scope_defs(self):
        self.assertEqual(entity.parse_scope_defs(SCOPES), {"ai_agent": {"entity": ["inc"], "field": ["inc2"]}})


class ExtractTest(unittest.TestCase):
    def test_test_framework_and_stub_entities_dropped(self):
        root = tempfile.mkdtemp()
        for sub in ("TestFrameworkBundle/Entity", "IntegrationBundle/Entity/Stub", "RealBundle/Entity"):
            os.makedirs(os.path.join(root, "src", sub))
            open(os.path.join(root, "src", sub, "Foo.php"), "w").write(ATTR)

        class C:
            def __init__(self):
                self.root = root

            def rel(self, p):
                return os.path.relpath(p, root)
        files = [r["file"] for r in entity.extract(C()) if r["kind"] != "config-scope"]
        self.assertEqual(files, [os.path.join("src", "RealBundle", "Entity", "Foo.php")])

    def test_extract_end_to_end(self):
        root = tempfile.mkdtemp()
        d = os.path.join(root, "src", "Acme", "Entity")
        os.makedirs(d)
        os.makedirs(os.path.join(root, "src", "Acme", "Tests"))
        open(os.path.join(d, "Foo.php"), "w").write(ATTR)
        open(os.path.join(root, "src", "Acme", "Tests", "T.php"), "w").write(ANN)
        cfg = os.path.join(root, "src", "Acme", "Resources", "config", "aaxis")
        os.makedirs(cfg)
        open(os.path.join(cfg, "entity_extend.yml"), "w").write(
            EXTEND.replace("Oro\\Bundle\\ProductBundle\\Entity\\Product", "Acme\\Bundle\\FooBundle\\Entity\\Foo")
        )

        class Ctx:
            pass

        ctx = Ctx()
        ctx.root = root
        ctx.rel = lambda p: os.path.relpath(p, root)
        recs = {r["id"]: r for r in entity.extract(ctx)}
        foo = recs["Acme\\Bundle\\FooBundle\\Entity\\Foo"]
        self.assertEqual(foo["repository_override"], "Buckman\\Repo\\ProductRepository")
        self.assertEqual(foo["file"], "src/Acme/Entity/Foo.php")
        self.assertIn("acme_foo", foo["keys"])
        self.assertNotIn("Acme\\Entity\\Bar", recs)
        self.assertEqual(recs["Buckman\\Entity\\Pub"]["kind"], "extend-override")


class TableNameTest(unittest.TestCase):
    def test_positional_and_nested_index_names(self):
        self.assertEqual(entity.table_name("#[ORM\\Table('oro_address')]\n#[ORM\\Index(name: 'i')]"), "oro_address")
        hdr = "#[ORM\\Table(indexes: [new ORM\\Index(name: 'idx', columns: ['a'])], name: 'real_tbl')]"
        self.assertEqual(entity.table_name(hdr), "real_tbl")
        self.assertIsNone(entity.table_name("#[ORM\\Entity]"))


if __name__ == "__main__":
    unittest.main()
