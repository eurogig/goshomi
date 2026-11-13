"""Exercise conflict-safe installation without touching real user skill directories."""
from contextlib import redirect_stderr, redirect_stdout
import importlib.util
from io import StringIO
from pathlib import Path
import sys
import subprocess
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/install-skill.py'
spec = importlib.util.spec_from_file_location('install_skill', SCRIPT)
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)

class InstallTest(unittest.TestCase):
    def test_standalone_copy_is_versioned_and_independent(self):
        with tempfile.TemporaryDirectory(prefix='tourrific-standalone-') as tmp:
            root = Path(tmp)
            checkout = root / 'checkout'
            checkout.mkdir()
            subprocess.run(['git', 'init', '-q', str(checkout)], check=True)
            for name, content in {'.agents/skills/tourrific/SKILL.md': 'skill', 'tools/tourrific/scripts/tour.py': 'script', 'tools/tourrific/schema/tour.schema.json': '{}', '.gitignore': 'dist/\n'}.items():
                path = checkout / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content)
            assets = checkout / 'tools/tourrific/viewer/dist/assets'
            assets.mkdir(parents=True)
            (assets / 'viewer.js').write_text('js')
            (assets / 'viewer.css').write_text('css')
            subprocess.run(['git', '-C', str(checkout), 'add', '.'], check=True)
            subprocess.run(['git', '-C', str(checkout), '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '-qm', 'fixture'], check=True)
            source = installer.standalone_source(checkout, root)
            self.assertEqual((source / 'SKILL.md').read_text(), 'skill')
            self.assertEqual((source / 'scripts/tour.py').read_text(), 'script')
            self.assertTrue((source / 'viewer/dist/assets/viewer.js').is_file())
            self.assertEqual(installer.standalone_source(checkout, root), source)
            (checkout / '.agents/skills/tourrific/SKILL.md').write_text('changed')
            self.assertEqual((source / 'SKILL.md').read_text(), 'skill')
            with self.assertRaises(ValueError): installer.standalone_source(checkout, root)

    def test_conflict_backup_and_idempotence(self):
        with tempfile.TemporaryDirectory(prefix='tourrific-install-') as tmp:
            root = Path(tmp)
            old = root / '.agents/skills/tourrific'
            old.mkdir(parents=True)
            (old / 'SKILL.md').write_text('old customized skill')
            claude = root / '.claude/skills/tourrific'
            def run(*args):
                with patch.object(sys, 'argv', [str(SCRIPT), '--agent', 'both', '--scope', 'user', *args]), patch.object(Path, 'home', return_value=root), redirect_stdout(StringIO()), redirect_stderr(StringIO()):
                    return installer.main()
            self.assertEqual(run(), 1)
            self.assertEqual((old / 'SKILL.md').read_text(), 'old customized skill')
            self.assertFalse(claude.exists())
            self.assertEqual(run('--replace'), 0)
            self.assertTrue(old.is_symlink())
            self.assertTrue(claude.is_symlink())
            self.assertEqual(old.resolve(), claude.resolve())
            backup = list((root / '.agents/tourrific-backups').glob('tourrific-*'))
            self.assertEqual(len(backup), 1)
            self.assertEqual((backup[0] / 'SKILL.md').read_text(), 'old customized skill')
            self.assertEqual(run(), 0)
            self.assertEqual(len(list((root / '.agents/tourrific-backups').glob('tourrific-*'))), 1)

if __name__ == '__main__': unittest.main()
