#!/usr/bin/env python3
"""Link the canonical skill into supported agent directories, preserving replaced skills."""
import argparse
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


def exists(path):
    return path.exists() or path.is_symlink()


def standalone_source(checkout, base):
    """Copy a clean commit and its built viewer into an immutable version directory."""
    def git(*args):
        return subprocess.run(['git', '-C', str(checkout), *args], capture_output=True, text=True, check=True).stdout.strip()
    commit = git('rev-parse', '--verify', 'HEAD^{commit}')
    if git('status', '--porcelain', '--untracked-files=normal'):
        raise ValueError('Standalone installation requires a clean checkout. Commit or discard changes first.')
    assets = checkout / 'tools/goshomi/viewer/dist/assets'
    if len(list(assets.glob('*.js'))) != 1 or len(list(assets.glob('*.css'))) != 1:
        raise ValueError('Build the viewer before standalone installation.')
    versions = base / '.local/share/goshomi/versions'
    versions.mkdir(parents=True, exist_ok=True)
    dest = versions / commit
    with tempfile.TemporaryDirectory(prefix='.install-', dir=versions) as tmp:
        stage = Path(tmp) / 'version'
        skill = stage / '.agents/skills/goshomi'
        skill.mkdir(parents=True)
        shutil.copy2(checkout / '.agents/skills/goshomi/SKILL.md', skill / 'SKILL.md')
        for name in ('scripts', 'schema', 'viewer'):
            (skill / name).symlink_to(f'../../../tools/goshomi/{name}', target_is_directory=True)
        target = stage / 'tools/goshomi'
        shutil.copytree(checkout / 'tools/goshomi/scripts', target / 'scripts', ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        shutil.copytree(checkout / 'tools/goshomi/schema', target / 'schema')
        shutil.copytree(checkout / 'tools/goshomi/viewer/dist', target / 'viewer/dist')
        def fingerprint(root):
            result = {}
            for path in root.rglob('*'):
                name = str(path.relative_to(root))
                if path.is_symlink(): result[name] = ('link', str(path.readlink()))
                elif path.is_file(): result[name] = ('file', hashlib.sha256(path.read_bytes()).hexdigest())
            return result
        if exists(dest):
            if dest.is_symlink() or not dest.is_dir() or fingerprint(dest) != fingerprint(stage):
                raise ValueError(f'Existing version differs from the built checkout: {dest}')
        else:
            stage.rename(dest)
    print(f'Installed version files: {dest}')
    return dest / '.agents/skills/goshomi'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--agent', choices=('codex', 'claude', 'both'), required=True)
    parser.add_argument('--scope', choices=('project', 'user'), required=True)
    parser.add_argument('--project', type=Path, help='Project directory (default: current directory); only for project scope')
    parser.add_argument('--replace', action='store_true', help='Back up existing conflicting skills before linking the current skill')
    parser.add_argument('--standalone', action='store_true', help='Copy a clean commit and built assets into a user-managed version directory')
    args = parser.parse_args()
    if args.scope == 'user' and args.project:
        parser.error('--project applies only to project scope')
    checkout = Path(__file__).resolve().parents[3]
    source = checkout / '.agents' / 'skills' / 'goshomi'
    if not (source / 'SKILL.md').is_file():
        parser.error(f'Canonical skill not found: {source}')
    base = (args.project or Path.cwd()).expanduser().resolve() if args.scope == 'project' else Path.home()
    if not base.is_dir():
        parser.error(f'Project directory does not exist: {base}')
    if args.standalone and args.scope != 'user':
        parser.error('--standalone requires --scope user')
    if args.standalone:
        try:
            source = standalone_source(checkout, base)
        except (OSError, ValueError, subprocess.CalledProcessError) as exc:
            print(f'Standalone installation failed: {exc}', file=sys.stderr)
            return 1
    agents = ('codex', 'claude') if args.agent == 'both' else (args.agent,)
    destinations = [base / ('.agents' if agent == 'codex' else '.claude') / 'skills' / 'goshomi' for agent in agents]
    conflicts = [dest for dest in destinations if exists(dest) and dest.resolve() != source.resolve()]
    if conflicts and not args.replace:
        for dest in conflicts:
            print(f'Existing skill: {dest}', file=sys.stderr)
        print('No active skills changed. Rerun with --replace to back up the existing skill and install the current one.', file=sys.stderr)
        return 1
    installed, backups = [], []
    try:
        for dest in destinations:
            if exists(dest) and dest.resolve() == source.resolve():
                print(f'Already installed: {dest}')
                continue
            if exists(dest):
                backup_dir = dest.parent.parent / 'goshomi-backups'
                backup_dir.mkdir(parents=True, exist_ok=True)
                stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
                backup = backup_dir / f'goshomi-{stamp}'
                if exists(backup):
                    raise FileExistsError(f'Backup destination already exists: {backup}')
                original_link = dest.readlink() if dest.is_symlink() else None
                if original_link is not None and not original_link.is_absolute():
                    backup.symlink_to(dest.resolve(), target_is_directory=True)
                    try:
                        dest.unlink()
                    except OSError:
                        backup.unlink()
                        raise
                else:
                    dest.rename(backup)
                backups.append((dest, backup, original_link))
                print(f'Backed up: {dest} -> {backup}')
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.symlink_to(source.resolve(), target_is_directory=True)
            installed.append(dest)
            print(f'Installed: {dest} -> {source.resolve()}')
    except OSError as exc:
        # Restore previous entries if a later installation fails.
        for dest in reversed(installed):
            try:
                dest.unlink()
            except OSError as rollback_error:
                print(f'Could not remove new link {dest}: {rollback_error}', file=sys.stderr)
        for dest, backup, original_link in reversed(backups):
            try:
                if original_link is not None and not original_link.is_absolute():
                    dest.symlink_to(original_link, target_is_directory=True)
                    backup.unlink()
                else:
                    backup.rename(dest)
            except OSError as rollback_error:
                print(f'Could not restore {backup} to {dest}: {rollback_error}', file=sys.stderr)
        print(f'Installation failed: {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
