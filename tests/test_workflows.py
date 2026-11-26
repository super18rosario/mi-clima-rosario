"""Reglas de concurrencia entre workflows (lectura de texto, sin PyYAML ni red)."""
import pathlib
import re
import unittest

WF = pathlib.Path(__file__).resolve().parents[1] / ".github" / "workflows"


def text(name):
    return (WF / name).read_text(encoding="utf-8")


def group(source):
    match = re.search(r"^concurrency:\s*\n\s+group:\s*(\S+)", source, re.M)
    return match.group(1) if match else None


class WorkflowConcurrencyTests(unittest.TestCase):
    def test_only_clima_and_rayos_deploy_pages_in_one_group(self):
        deployers = sorted(p.name for p in WF.glob("*.yml") if "deploy-pages" in p.read_text(encoding="utf-8"))
        self.assertEqual(deployers, ["clima.yml", "rayos.yml"])
        self.assertEqual(group(text("clima.yml")), group(text("rayos.yml")))
        for name in deployers:
            self.assertRegex(text(name), r"cancel-in-progress:\s*false")

    def test_rosariosc_commits_only_and_has_own_queue(self):
        source = text("rosariosc.yml")
        self.assertNotIn("deploy-pages", source)
        self.assertNotIn("pages: write", source)
        self.assertNotEqual(group(source), group(text("clima.yml")))
        self.assertIn("data/rosariosc_history", source)

    def test_every_pushing_workflow_retries_and_skips_ci(self):
        for path in WF.glob("*.yml"):
            source = path.read_text(encoding="utf-8")
            if "git push" not in source:
                continue
            with self.subTest(path.name):
                self.assertRegex(source, r"for intento in 1 2 3")
                for message in re.findall(r"git commit -m '([^']+)'", source):
                    self.assertIn("[skip ci]", message)

    def test_publishers_sync_main_before_building_page(self):
        for name in ("clima.yml", "rayos.yml"):
            source = text(name)
            self.assertLess(source.index("git reset --hard origin/main\n      - name: Preparar"),
                            source.index("cp -R data _publish/"))

    def test_diagnostics_are_read_only(self):
        for path in WF.glob("*.yml"):
            if path.name in ("clima.yml", "rayos.yml", "rosariosc.yml", "recuperar-historico.yml"):
                continue
            with self.subTest(path.name):
                source = path.read_text(encoding="utf-8")
                self.assertIn("contents: read", source)
                self.assertNotIn("git push", source)

    def test_history_recovery_shares_rosariosc_queue_and_is_manual(self):
        source = text("recuperar-historico.yml")
        self.assertEqual(group(source), group(text("rosariosc.yml")))
        self.assertNotIn("schedule", source)
        self.assertNotIn("deploy-pages", source)
        self.assertNotIn("secrets.", source)
        self.assertIn("fetch-depth: 0", source)

    def test_pull_request_tests_are_read_only(self):
        source = text("pruebas.yml")
        self.assertIn("pull_request", source)
        self.assertIn("contents: read", source)
        self.assertNotIn("git push", source)

if __name__ == "__main__":
    unittest.main()
