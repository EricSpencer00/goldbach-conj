import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from run_manifest import ManifestError, verify_manifest


ROOT = Path(__file__).parents[1]


class RunManifestTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)

    def make_project(self, name: str) -> Path:
        project = Path(self.temp_dir.name) / name
        (project / "runs").mkdir(parents=True)
        for filename in ("generate_thru_n.py", "goldbach_check.py", "run_manifest.py"):
            shutil.copy2(ROOT / filename, project / filename)
        return project

    def generate(self, project: Path) -> tuple[Path, Path]:
        artifact = project / "runs" / "sample.txt"
        manifest = project / "runs" / "sample.json"
        subprocess.run(
            [
                sys.executable,
                "generate_thru_n.py",
                "--max-n",
                "1000",
                "--output",
                "runs/sample.txt",
                "--manifest",
                "runs/sample.json",
            ],
            cwd=project,
            check=True,
            capture_output=True,
            text=True,
        )
        return artifact, manifest

    def test_clean_reproductions_have_identical_artifacts_and_manifests(self) -> None:
        first_artifact, first_manifest = self.generate(self.make_project("first"))
        second_artifact, second_manifest = self.generate(self.make_project("second"))

        self.assertEqual(first_artifact.read_bytes(), second_artifact.read_bytes())
        self.assertEqual(
            json.loads(first_manifest.read_text(encoding="utf-8")),
            json.loads(second_manifest.read_text(encoding="utf-8")),
        )
        payload = verify_manifest(first_manifest)
        self.assertEqual(payload["range"], {"end": 1000, "records": 499, "start": 4})

    def test_generated_small_run_preserves_checked_in_output(self) -> None:
        project = self.make_project("compatibility")
        artifact, _ = self.generate(project)

        self.assertEqual(
            artifact.read_bytes(),
            (ROOT / "runs" / "thru1-000.txt").read_bytes(),
        )

    def test_artifact_tampering_fails_verification(self) -> None:
        project = self.make_project("artifact-tamper")
        artifact, manifest = self.generate(project)
        original = artifact.read_bytes()
        artifact.write_bytes(original.replace(b"4 = 2 + 2", b"4 = 2 + 3", 1))

        with self.assertRaises(ManifestError):
            verify_manifest(manifest)

    def test_source_tampering_fails_verification(self) -> None:
        project = self.make_project("source-tamper")
        _, manifest = self.generate(project)
        generator = project / "generate_thru_n.py"
        generator.write_bytes(generator.read_bytes() + b"\n")

        with self.assertRaises(ManifestError):
            verify_manifest(manifest)

    def test_checked_in_million_run_manifest_is_valid(self) -> None:
        payload = verify_manifest(ROOT / "runs" / "thru1-000-000.json")

        self.assertEqual(payload["range"], {
            "end": 1_000_000,
            "records": 499_999,
            "start": 4,
        })


if __name__ == "__main__":
    unittest.main()
