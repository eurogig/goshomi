#!/usr/bin/env python3
"""Link the canonical skill into supported agent directories, preserving replaced skills."""
import argparse
from datetime import datetime, timezone
from pathlib import Path
import sys


def exists(path):
    return path.exists() or path.is_symlink()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--agent', choices=('codex', 'claude', 'both'), required=True)
    parser.add_argument('--scope', choices=('project', 'user'), required=True)
    parser.add_argument('--project', type=Path, help='Project directory (default: current directory); only for project scope')
    parser.add_argument('--replace', action='store_true', help='Back up existing conflicting skills before linking the current skill')
    args = parser.parse_args()
    if args.scope == 'user' and args.project:
        parser.error('--project applies only to project scope')
    source = Path(__file__).resolve().parents[3] / '.agents' / 'skills' / 'tourrific'
    if not (source / 'SKILL.md').is_file():
        parser.error(f'Canonical skill not found: {source}')
    base = (args.project or Path.cwd()).expanduser().resolve() if args.scope == 'project' else Path.home()
    if not base.is_dir():
        parser.error(f'Project directory does not exist: {base}')
    agents = ('codex', 'claude') if args.agent == 'both' else (args.agent,)
    destinations = [base / ('.agents' if agent == 'codex' else '.claude') / 'skills' / 'tourrific' for agent in agents]
    conflicts = [dest for dest in destinations if exists(dest) and dest.resolve() != source.resolve()]
    if conflicts and not args.replace:
        for dest in conflicts:
            print(f'Existing skill: {dest}', file=sys.stderr)
        print('Nothing changed. Rerun with --replace to back up the existing skill and install the current one.', file=sys.stderr)
        return 1
    installed, backups = [], []
    try:
        for dest in destinations:
            if exists(dest) and dest.resolve() == source.resolve():
                print(f'Already installed: {dest}')
                continue
            if exists(dest):
                backup_dir = dest.parent.parent / 'tourrific-backups'
                backup_dir.mkdir(parents=True, exist_ok=True)
                stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
                backup = backup_dir / f'tourrific-{stamp}'
                if exists(backup):
                    raise FileExistsError(f'Backup destination already exists: {backup}')
                dest.rename(backup)
                backups.append((dest, backup))
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
        for dest, backup in reversed(backups):
            try:
                backup.rename(dest)
            except OSError as rollback_error:
                print(f'Could not restore {backup} to {dest}: {rollback_error}', file=sys.stderr)
        print(f'Installation failed: {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
