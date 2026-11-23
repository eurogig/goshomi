# Tourrific — Your Code. Explained.

Tourrific produces a source-grounded architectural tour and a lightweight threat model for a local repository. An agent performs the semantic analysis; the agent-independent Python scripts validate and package the evidence, and the React viewer presents it. No target code is executed.

## Install once

For an installation independent of a development checkout, follow the installer instructions in the [root README](../../README.md). The installer copies a clean Git commit and built viewer to `~/.local/share/tourrific/versions/<commit>/`. Updating to a different commit is explicit and requires `--replace`; the previous skill links are backed up. A commit identifies the source, not a signed or reproducible build, so review the source and dependencies you build. No release tag is created by the installer.

Keep a Tourrific checkout as the portable dependency. From its root, install the viewer's build dependencies and build its reusable assets:

```sh
npm install --prefix tools/tourrific/viewer
npm --prefix tools/tourrific/viewer run build
```

Install the shared skill for Codex and Claude Code at user level:

```sh
python3 tools/tourrific/scripts/install-skill.py --agent both --scope user
```

This links the canonical `.agents/skills/tourrific/` directory into `~/.agents/skills/tourrific/` and `~/.claude/skills/tourrific/`. The skill contains links to its scripts, schema, and built viewer in the checkout; keep that checkout in place. Use `--agent codex` or `--agent claude` to install for one agent. If an old copy already exists, the installer stops without changing it. To back it up and install the current skill, rerun the same command with `--replace` (for example, `python3 tools/tourrific/scripts/install-skill.py --agent both --scope user --replace`). The previous directory is moved to `~/.agents/tourrific-backups/` or `~/.claude/tourrific-backups/`, outside the active skill directories. Rebuild the viewer when its source changes; the target repository needs neither npm nor a copy of the application.

Project-scope installation is also available:

```sh
python3 tools/tourrific/scripts/install-skill.py --agent both --scope project --project /path/to/project
```

Omit `--project` for the current directory. Project installation deliberately adds links to that project; user-level installation avoids that change. Restart or reload the agent if necessary for discovery. Symlinks require filesystem support and permissions.

## Generate a tour

From the project you want to understand, invoke **`$tourrific`** in Codex or **`/tourrific`** in Claude Code. The skill uses the current project's Git root, or the current directory outside Git. Ask for `--repo /path/to/project` to select a different target, or `--output /path/to/output` to choose an output directory. The Tourrific source checkout itself must be explicitly selected with `--repo` before generating a tour there.

Before generating or reusing a tour, the skill checks whether its output is exposed to Git. If it is not ignored, the skill asks whether to add an ignore rule or use another location; it separately warns about files already tracked by Git. Ignore rules do not remove tracked files or prevent force-adds. The same check applies to custom output inside any Git repository. You can inspect the result with `python3 "$SKILL_DIR/scripts/tour.py" output-status` and the same `--repo` and `--output` options.

When an existing tour has a matching repository snapshot and intact generated files, the skill reuses it and starts the preview immediately. Otherwise the agent indexes the target and authors an evidence-based narrative; the scripts cannot infer that narrative by themselves. Ask to regenerate or refresh explicitly to bypass reuse. The skill packages the result into `<target>/.tourrific/` by default:

```text
.tourrific/
  index.html                 # served by the local preview server
  tour.json                  # structured tour and cited excerpts
  analysis.json              # agent-authored narrative, when saved here
  assets/                    # compiled viewer
  sources/                   # cited source excerpts only
  .tourrific-owner.json      # repository identity and managed-file list
```

After generating a tour, the skill starts a loopback-only preview server and gives you its URL; it does not launch a browser or computer use. To start the server yourself from the target repository, run:

```sh
python3 -u -m http.server --bind 127.0.0.1 --directory .tourrific 0
```

Open the URL printed by the server. Port `0` asks the operating system to select an available port. With a custom output, substitute its path for `.tourrific`. Press Ctrl+C in the server terminal when finished. In a remote environment, use an available forwarded URL to access the server.

Select a chapter and use Next stop or the step markers. Select a diagram component to inspect its description, relationships and source; use source tabs to switch references. The square diagram control fits the map to its frame. Use **Expand map** for a larger view, then Close or Escape to return; selecting a component also returns to its source. On narrow screens, use the Tour and Source tabs. Chapter 7 reviews deterministic code-level findings, including reachability, a proposed fix example, and a copyable fix prompt. Chapter 8 presents threat-model scenarios with their qualitative risk level, reasoning, evidence, controls, and relevant OWASP or MITRE references. Each finding includes a suggested mitigation prompt you can review and copy into your coding agent; Tourrific never runs the prompt. When the source supports LLM or agentic functionality, the agent considers the applicable [OWASP Top 10 for LLM Applications 2026](https://genai.owasp.org/resource/owasp-genai-llm-top-10-2026/) and [OWASP Top 10 for Agentic Applications 2026](https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/), using evidence-based, conditional mappings. This is not a comprehensive security scan. When a scenario includes an authored path, red dashed arrows show the possible sequence; they do not establish an exploit.

## Command-line workflow

The agent normally runs these commands after producing an analysis. `SKILL_DIR` below is the installed skill directory for either agent; it is not the target repository. Run from the target project, or append the same `--repo` and `--output` options to each command.

```sh
python3 "$SKILL_DIR/scripts/tour.py" check  # If current, start the preview; otherwise analyze.
BASELINE=$(python3 "$SKILL_DIR/scripts/tour.py" snapshot)
python3 "$SKILL_DIR/scripts/tour.py" index
python3 "$SKILL_DIR/scripts/tour.py" prepare
# Author .tourrific/analysis.json using "$SKILL_DIR/schema/tour.schema.json".
# After completing the security path review and threat review, including AI applicability and self-contained remediation prompts:
python3 "$SKILL_DIR/scripts/tour.py" package --analysis .tourrific/analysis.json --baseline "$BASELINE" --review-policy self-contained-remediation-2026-v3
python3 "$SKILL_DIR/scripts/tour.py" verify
```

`prepare` creates or checks the output's ownership marker before an agent writes an analysis. Packaging checks ownership, schema, references and symbols before writing managed files. It refuses to use a nonempty unowned directory, another repository's output, a symlinked output directory, or existing unmanaged files. On regeneration it replaces only previously managed files and removes stale managed snapshots within that output. The marker identifies the target using a hash of its resolved path, not the path itself. Moving a repository changes its identity: choose a fresh output directory or consciously remove the old output yourself before regenerating.

For a non-Git target or a repository with submodules, omit the `snapshot` command and `--baseline`; such tours are not automatically reused.

`check` compares the snapshot captured before analysis with the current Git revision, index, tracked and untracked files, and source files eligible for indexing, including eligible Git-ignored source files. It also checks the integrity of generated viewer files. Generated output is excluded; other Git-ignored files outside the index are not tracked. The snapshot contains hashes, not source contents. Older tours without a pre-analysis snapshot, risk assessments, mitigation prompts, or the current security path review are regenerated once. `--review-policy` records the agent’s attestation that it completed the security path and applicability reviews; the packager checks referenced paths and line ranges in new remediation prompts, but does not establish prompt completeness or correctness; this is not automated proof of coverage and must not be used to mark an old analysis as reviewed. Non-Git targets and repositories containing submodules are analyzed normally but are not automatically reused. If Git or source inspection fails, the check does not claim the tour is current. `verify` separately compares cited excerpts and the Git revision with the target. Re-run semantic analysis after changes; packaging alone does not update explanations. The source snapshots blank uncited lines to preserve line numbers. Tour data and the viewer contain the same cited excerpts, so inspect them before sharing.

## Safety and limits

The indexer excludes common generated and dependency directories, `.tourrific`, environment files, binary and large files, and symlinks. Packaging rejects common secret patterns and developer-specific absolute home paths, but these checks are heuristic, not a guarantee. Symbols are matched as text in cited ranges rather than parsed. A tour is a scoped interpretation of source, not a penetration test or complete security review. The validator implements the JSON Schema keywords used by the supplied schema and checks cross-links.
