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
        with tempfile.TemporaryDirectory(prefix='goshomi-standalone-') as tmp:
            root = Path(tmp)
            checkout = root / 'checkout'
            checkout.mkdir()
            subprocess.run(['git', 'init', '-q', str(checkout)], check=True)
            for name, content in {'.agents/skills/goshomi/SKILL.md': 'skill', 'tools/goshomi/scripts/tour.py': 'script', 'tools/goshomi/schema/tour.schema.json': '{}', '.gitignore': 'dist/\n'}.items():
                path = checkout / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content)
            assets = checkout / 'tools/goshomi/viewer/dist/assets'
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
            (checkout / '.agents/skills/goshomi/SKILL.md').write_text('changed')
            self.assertEqual((source / 'SKILL.md').read_text(), 'skill')
            with self.assertRaises(ValueError): installer.standalone_source(checkout, root)

    def test_conflict_backup_and_idempotence(self):
        with tempfile.TemporaryDirectory(prefix='goshomi-install-') as tmp:
            root = Path(tmp)
            old = root / '.agents/skills/goshomi'
            old.mkdir(parents=True)
            (old / 'SKILL.md').write_text('old customized skill')
            claude = root / '.claude/skills/goshomi'
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
            backup = list((root / '.agents/goshomi-backups').glob('goshomi-*'))
            self.assertEqual(len(backup), 1)
            self.assertEqual((backup[0] / 'SKILL.md').read_text(), 'old customized skill')
            self.assertEqual(run(), 0)
            self.assertEqual(len(list((root / '.agents/goshomi-backups').glob('goshomi-*'))), 1)

    def test_relative_symlink_backup_and_rollback(self):
        with tempfile.TemporaryDirectory(prefix='goshomi-links-') as tmp:
            root = Path(tmp)
            original = root / '.agents/skills/old-skill'
            original.mkdir(parents=True)
            (original / 'SKILL.md').write_text('old')
            dest = original.parent / 'goshomi'
            dest.symlink_to('old-skill', target_is_directory=True)
            claude = root / '.claude/skills/goshomi'
            def run():
                with patch.object(sys, 'argv', [str(SCRIPT), '--agent', 'both', '--scope', 'user', '--replace']), patch.object(Path, 'home', return_value=root), redirect_stdout(StringIO()), redirect_stderr(StringIO()):
                    return installer.main()
            real_symlink = Path.symlink_to
            def fail_second(path, target, *args, **kwargs):
                if path == claude:
                    raise OSError('simulated failure')
                return real_symlink(path, target, *args, **kwargs)
            with patch.object(Path, 'symlink_to', fail_second):
                self.assertEqual(run(), 1)
            self.assertEqual(dest.readlink(), Path('old-skill'))
            self.assertEqual((dest / 'SKILL.md').read_text(), 'old')
            self.assertFalse(claude.exists())
            self.assertEqual(run(), 0)
            backup = next((root / '.agents/goshomi-backups').glob('goshomi-*'))
            self.assertEqual((backup / 'SKILL.md').read_text(), 'old')

    def test_bootstrap_installs_from_git_checkout(self):
        bootstrap_spec = importlib.util.spec_from_file_location('bootstrap', SCRIPT.parents[3] / 'install.py')
        bootstrap = importlib.util.module_from_spec(bootstrap_spec)
        bootstrap_spec.loader.exec_module(bootstrap)
        with tempfile.TemporaryDirectory(prefix='goshomi-bootstrap-') as tmp:
            root = Path(tmp)
            repo = root / 'repo'
            repo.mkdir()
            subprocess.run(['git', 'init', '-q', '-b', 'main', str(repo)], check=True)
            files = {'.agents/skills/goshomi/SKILL.md': 'skill',
                     'tools/goshomi/scripts/tour.py': 'script',
                     'tools/goshomi/schema/tour.schema.json': '{}',
                     '.gitignore': 'dist/\n'}
            for name, content in files.items():
                path = repo / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content)
            target = repo / 'tools/goshomi/scripts/install-skill.py'
            target.write_text(SCRIPT.read_text())
            subprocess.run(['git', '-C', str(repo), 'add', '.'], check=True)
            subprocess.run(['git', '-C', str(repo), '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '-qm', 'fixture'], check=True)
            real_run = subprocess.run
            def run(command, **kwargs):
                if command[0] == 'npm':
                    if command[1] == 'run':
                        assets = Path(command[-1]) / 'dist/assets'
                        assets.mkdir(parents=True)
                        (assets / 'viewer.js').write_text('js')
                        (assets / 'viewer.css').write_text('css')
                    return subprocess.CompletedProcess(command, 0)
                return real_run(command, **kwargs)
            with patch.object(bootstrap, 'REPOSITORY', str(repo)), patch.object(sys, 'argv', ['install.py', '--agent', 'codex']), patch.dict('os.environ', {'HOME': str(root)}), patch.object(subprocess, 'run', side_effect=run):
                self.assertEqual(bootstrap.main(), 0)
            installed = root / '.agents/skills/goshomi'
            self.assertEqual((installed / 'SKILL.md').read_text(), 'skill')
            self.assertTrue((installed / 'viewer/dist/assets/viewer.js').is_file())
            self.assertTrue((installed / 'scripts/tour.py').is_file())

if __name__ == '__main__': unittest.main()
