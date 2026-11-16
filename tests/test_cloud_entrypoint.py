"""Cloud-style entrypoint regression tests; no credentials or network required."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

ROOT = Path(__file__).resolve().parents[1]


class CloudEntrypointTests(unittest.TestCase):
    def test_entrypoint_imports_without_repository_on_sys_path(self):
        entrypoint = ROOT / 'dashboard/app.py'
        probe = (
            "import runpy, sys; from pathlib import Path; "
            f"root = Path({str(ROOT)!r}); "
            "sys.path = [p for p in sys.path if p and Path(p).resolve() != root]; "
            "sys.path.insert(0, str(root / 'dashboard')); "
            f"runpy.run_path({str(entrypoint)!r}, run_name='cloud_import_probe'); "
            "import dashboard.bigquery_reader, dashboard.check_job, checker.assessment; "
            "assert Path(dashboard.bigquery_reader.__file__).resolve().parents[1] == root; "
            "assert Path(checker.assessment.__file__).resolve().parents[1] == root; "
            "print('entrypoint import passed')"
        )
        with tempfile.TemporaryDirectory() as elsewhere:
            for cwd in (ROOT, ROOT / 'dashboard', Path(elsewhere)):
                with self.subTest(launch_directory=cwd.name):
                    result = subprocess.run([sys.executable, '-I', '-c', probe], cwd=cwd,
                                            capture_output=True, text=True, timeout=45)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertIn('entrypoint import passed', result.stdout)

    def test_cloud_requirements_include_complete_runtime_without_cycles(self):
        def read(path, ancestors=()):
            path = path.resolve()
            self.assertNotIn(path, ancestors, 'Circular requirements include')
            requirements = set()
            for line in path.read_text().splitlines():
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if line.startswith('-r '):
                    requirements |= read(path.parent / line[3:].strip(), (*ancestors, path))
                else:
                    requirements.add(canonicalize_name(Requirement(line).name))
            return requirements
        cloud = read(ROOT / 'dashboard/requirements.txt')
        self.assertTrue({'streamlit', 'pandas', 'google-cloud-bigquery', 'scikit-learn',
                         'joblib', 'tldextract', 'jinja2'} <= cloud)
        self.assertEqual(read(ROOT / 'checker/requirements.txt'), cloud)


if __name__ == '__main__':
    unittest.main()
