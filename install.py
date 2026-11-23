#!/usr/bin/env python3
"""Install a standalone Goshomi skill from GitHub using Git, Node.js, and Python."""
import argparse
from pathlib import Path
import subprocess
import sys
import tempfile

REPOSITORY = 'https://github.com/eurogig/tourrific.git'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--agent', choices=('codex', 'claude', 'both'), default='both')
    parser.add_argument('--ref', default='main', help='Git branch, tag, or commit to install (default: main)')
    parser.add_argument('--replace', action='store_true', help='Back up and replace an existing skill')
    args = parser.parse_args()
    try:
        with tempfile.TemporaryDirectory(prefix='goshomi-install-') as tmp:
            checkout = Path(tmp) / 'checkout'
            subprocess.run(['git', 'clone', '--no-checkout', '--', REPOSITORY, str(checkout)], check=True)
            commit = subprocess.run(['git', '-C', str(checkout), 'rev-parse', '--verify',
                                     '--end-of-options', f'{args.ref}^{{commit}}'],
                                    check=True, capture_output=True, text=True).stdout.strip()
            subprocess.run(['git', '-C', str(checkout), 'checkout', '--detach', commit], check=True)
            viewer = checkout / 'tools/goshomi/viewer'
            subprocess.run(['npm', 'ci', '--prefix', str(viewer)], check=True)
            subprocess.run(['npm', 'run', 'build', '--prefix', str(viewer)], check=True)
            command = [sys.executable, str(checkout / 'tools/goshomi/scripts/install-skill.py'),
                       '--agent', args.agent, '--scope', 'user', '--standalone']
            if args.replace:
                command.append('--replace')
            subprocess.run(command, check=True)
    except (OSError, subprocess.CalledProcessError) as exc:
        print(f'Installation failed: {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
