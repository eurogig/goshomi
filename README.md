# Tourrific

Tourrific turns a codebase into an interactive, source-grounded architectural tour and lightweight threat model. An AI coding agent examines the repository and writes the narrative; Tourrific's scripts validate and package the evidence, and a local viewer presents it. The indexer does not execute the target project's code.

![Tourrific Chapter 8 threat model with an attack path and linked source evidence](assets/tourrific-screenshot.png)

## Install

Install for Codex and Claude Code with Python 3, Git, Node.js, and npm installed:

```sh
curl -fsSLO https://raw.githubusercontent.com/eurogig/tourrific/main/install.py
python3 install.py
```

The installer downloads the repository into a temporary directory, builds the viewer, and installs an independent copy under `~/.local/share/tourrific/versions/`. It links the skill for both agents; use `--agent codex` or `--agent claude` for just one. Restart the agent to discover the skill. You can delete `install.py` after installation.

To update or replace an existing installation, run `python3 install.py --replace`. Conflicting skills are backed up outside the active skill directories. To pin a reviewed commit or tag, pass `--ref <commit-or-tag>`; the default is `main`. Review the installer and source before running them. Building requires network access to GitHub and the configured npm registry.

For development, install directly from a checkout after building the viewer:

```sh
python3 tools/tourrific/scripts/install-skill.py --agent codex --scope user
python3 tools/tourrific/scripts/install-skill.py --agent claude --scope user
# Or install for both agents:
python3 tools/tourrific/scripts/install-skill.py --agent both --scope user
```

The installer links the skill to this checkout, so keep the cloned repository in place. User scope installs for your account. To install into one project instead, run from that project and use `--scope project`; for example:

```sh
python3 /path/to/tourrific/tools/tourrific/scripts/install-skill.py --agent both --scope project
```

If an installation already exists, the installer leaves it alone. Use `--replace` to back up a conflicting installation and install this copy.

## Generate a tour

Open the repository you want to understand in Codex or Claude Code and invoke the `tourrific` skill. You can also ask the agent to use `--repo /path/to/repository` for another local repository, or `--output /path/to/output` for a custom output location.

Chapter 7 reviews code-level vulnerabilities with evidence, reachability, and proposed fixes. When a validated patch is available, Chapter 7 offers a preview and download for review; patches are never applied automatically. Chapter 8 presents the broader threat model. The skill reuses a valid tour when its repository snapshot still matches. Ask it to regenerate or refresh the tour to force a fresh analysis. Generated tours go in `.tourrific/` by default. Before writing, the skill checks Git exposure and asks how to protect output that is not ignored. The agent starts a local preview server and returns its URL; it does not open a browser automatically.

## What's included

- `.agents/skills/tourrific/`: the canonical skill instructions, linked to the packaged resources below.
- `tools/tourrific/scripts/`: repository indexing, packaging, verification, and installation commands.
- `tools/tourrific/schema/`: the tour data schema.
- `tools/tourrific/viewer/`: the interactive tour viewer.
- `tools/tourrific/README.md`: the full workflow and command reference.

Tourrific's threat model is a source-based review, not a penetration test or security certification. Its conclusions depend on the files and deployment context available to the agent.

## Development

Run the viewer locally with:

```sh
npm run dev --prefix tools/tourrific/viewer
```

Run the Python checks with:

```sh
python3 -m unittest discover -s tools/tourrific/tests
```

See [`tools/tourrific/README.md`](tools/tourrific/README.md) for detailed installation, generation, and safety notes.
