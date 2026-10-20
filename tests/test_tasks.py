import tempfile
import unittest
from collections import Counter
from pathlib import Path

import yaml

from tiganeval.runner import copy_workspace
from tiganeval.tasks import load_task, select_tasks


class TaskPackagesTest(unittest.TestCase):
    def test_selected_packages_and_reference_workspaces(self):
        tasks = [load_task(p) for p in select_tasks()]
        self.assertEqual(Counter(t.domain for t in tasks), {"SWE": 40, "Research": 24})
        manifests = [yaml.safe_load((t.root / "task.yaml").read_text()) for t in tasks]
        self.assertEqual(
            {m["id"] for m in manifests if "seed_sources" not in m},
            {"Research-cycle-life-drift", "Research-rollout-logging-gaps"},
        )
        self.assertEqual(
            len(
                {
                    m["seed_sources"][0]["name"]
                    for m in manifests
                    if m["domain"] == "SWE"
                }
            ),
            40,
        )
        for task in tasks:
            with self.subTest(task=task.task_id):
                self.assertNotIn("-v2-", task.task_id)
                self.assertNotIn("-pilot-", task.task_id)
                for variant in ("starter", "gold_workspace", "literal_workspace"):
                    with (
                        self.subTest(variant=variant),
                        tempfile.TemporaryDirectory() as directory,
                    ):
                        workspace = Path(directory) / "workspace"
                        copy_workspace(task.root / "workspace", workspace)
                        if variant != "starter":
                            overlay = task.root / "private" / variant
                            self.assertTrue(overlay.is_dir())
                            for path in overlay.rglob("*"):
                                if path.is_file() and "__pycache__" not in path.parts:
                                    target = workspace / path.relative_to(overlay)
                                    target.parent.mkdir(parents=True, exist_ok=True)
                                    target.write_bytes(path.read_bytes())
                        results = task.evaluate(workspace)
                        self.assertEqual(len(results), 5)
                        self.assertEqual(
                            all(r.passed for r in results), variant == "gold_workspace"
                        )
                        for result in results:
                            if result.passed:
                                continue
                            for occurrence in (1, 2, 3):
                                _, payload = task.registry.select(
                                    result.rubric_id,
                                    result.failure_mode,
                                    occurrence,
                                    observed=result.details.get("observed", {}),
                                )
                                self.assertTrue(payload["context"])
                                self.assertEqual("note" in payload, occurrence == 3)


if __name__ == "__main__":
    unittest.main()
