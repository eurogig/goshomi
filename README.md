# 示 goshomi

**GO SHOW ME.**

Understand the architecture. Reveal the risks.

Goshomi turns a codebase into an interactive, source-grounded architectural tour and lightweight threat model. An AI coding agent examines the repository and writes the narrative; Goshomi's scripts validate and package the evidence, and a local viewer presents it. The indexer does not execute the target project's code.

![Tour preview showing a threat model and source evidence](assets/tourrific-screenshot.png)

*The screenshot shows the previous Tourrific branding.*

## Install

The GitHub installer below will install Goshomi after these changes are published to the repository.

Install for Codex and Claude Code with Python 3, Git, Node.js, and npm installed:

```sh
(
  tmpdir=$(mktemp -d) || exit 1
  trap 'rm -rf "$tmpdir"' EXIT
  curl -fsSL https://raw.githubusercontent.com/eurogig/goshomi/main/install.py -o "$tmpdir/install.py" || exit 1
  python3 "$tmpdir/install.py"
)
```

The installer downloads the repository into a temporary directory, builds the viewer, and installs an independent copy under `~/.local/share/goshomi/versions/`. It links the skill for both agents; use `--agent codex` or `--agent claude` for just one. Restart the agent to discover the skill. The downloaded installer and temporary build files are removed automatically.

To update or replace an existing installation, run the same command with `--replace` after `"$tmpdir/install.py"`. Conflicting Goshomi skills are backed up outside the active skill directories. Existing `tourrific` skills are separate and must be removed or backed up manually when you migrate. To pin a reviewed commit or tag, pass `--ref <commit-or-tag>`; the default is `main`. Review the installer and source before running them. Building requires network access to GitHub and the configured npm registry.

For development, install directly from a checkout after building the viewer:

```sh
python3 tools/goshomi/scripts/install-skill.py --agent codex --scope user
python3 tools/goshomi/scripts/install-skill.py --agent claude --scope user
# Or install for both agents:
python3 tools/goshomi/scripts/install-skill.py --agent both --scope user
```

The installer links the skill to this checkout, so keep the cloned repository in place. User scope installs for your account. To install into one project instead, run from that project and use `--scope project`; for example:

```sh
python3 /path/to/goshomi/tools/goshomi/scripts/install-skill.py --agent both --scope project
```

If an installation already exists, the installer leaves it alone. Use `--replace` to back up a conflicting installation and install this copy.

## Generate a tour

Open the repository you want to understand in Codex or Claude Code and invoke the `goshomi` skill. You can also ask the agent to use `--repo /path/to/repository` for another local repository, or `--output /path/to/output` for a custom output location.

Chapter 7 reviews code-level vulnerabilities with evidence, reachability, and proposed fixes. When a validated patch is available, Chapter 7 offers a preview and download for review; patches are never applied automatically. Chapter 8 presents the broader threat model. The skill reuses a valid tour when its repository snapshot still matches. Ask it to regenerate or refresh the tour to force a fresh analysis. Generated tours go in `.goshomi/` by default. Existing `.tourrific/` tours are left in place; regenerate them to create Goshomi tours. Before writing, the skill checks Git exposure and asks how to protect output that is not ignored. The agent starts a local preview server and returns its URL; it does not open a browser automatically.

## What's included

- `.agents/skills/goshomi/`: the canonical skill instructions, linked to the packaged resources below.
- `tools/goshomi/scripts/`: repository indexing, packaging, verification, and installation commands.
- `tools/goshomi/schema/`: the tour data schema.
- `tools/goshomi/viewer/`: the interactive tour viewer.
- `tools/goshomi/README.md`: the full workflow and command reference.

Goshomi's threat model is a source-based review, not a penetration test or security certification. Its conclusions depend on the files and deployment context available to the agent.

## Development

Run the viewer locally with:

```sh
npm run dev --prefix tools/goshomi/viewer
```

Run the Python checks with:

```sh
python3 -m unittest discover -s tools/goshomi/tests
```

See [`tools/goshomi/README.md`](tools/goshomi/README.md) for detailed installation, generation, and safety notes.
