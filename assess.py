#!/usr/bin/env python3
"""Run the repository assessment agents with the Codex CLI."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
AGENTS_DIR = ROOT / "agents"
ASSESSMENT_DIR = ROOT / "assessment"

# The role names determine the report names. The reviewer filenames preserve the
# names already used by this repository.
AGENTS = {
    "architect": AGENTS_DIR / "architect.md",
    "security": AGENTS_DIR / "security_reviewer.md",
    "tester": AGENTS_DIR / "tester_reviewer.md",
    "privacy": AGENTS_DIR / "privacy_reviewer.md",
}

LEAD_INSTRUCTIONS = """\
You are the lead reviewer for this project. Below are four independent assessment
reports produced by specialist reviewers. Combine them into one actionable
engineering backlog.

Deduplicate overlapping findings, reconcile conflicting recommendations, and do
not invent evidence that is not present in the reports. Prioritise work by risk
and impact. For every backlog item include its priority, the problem, the
recommended action, and acceptance criteria. Preserve useful file and line
references. Finish with a suggested implementation order and clearly identify
anything that needs manual verification.
"""

OUTPUT_INSTRUCTIONS = """\

Orchestration note: work in read-only mode. Do not create or edit any files,
even if the role instructions above name an output file. Return the complete
Markdown report as your final answer; the orchestration script will save it.
"""


def run_codex(codex: str, prompt: str, output_path: Path) -> None:
    """Run one non-interactive, read-only Codex session."""
    command = [
        codex,
        "exec",
        "--sandbox",
        "read-only",
        "--cd",
        str(ROOT),
        "--ephemeral",
        "--color",
        "never",
        "--output-last-message",
        str(output_path),
        "-",
    ]
    subprocess.run(command, input=prompt, text=True, check=True)


def build_lead_prompt(reports: dict[str, str]) -> str:
    sections = [LEAD_INSTRUCTIONS]
    for name, report in reports.items():
        sections.append(f"\n## {name.title()} report\n\n{report}")
    return "".join(sections)


def main() -> int:
    codex = shutil.which("codex")
    if codex is None:
        print("Error: codex CLI was not found on PATH.", file=sys.stderr)
        return 1

    missing = [str(path.relative_to(ROOT)) for path in AGENTS.values() if not path.is_file()]
    if missing:
        print(f"Error: missing agent instruction file(s): {', '.join(missing)}", file=sys.stderr)
        return 1

    ASSESSMENT_DIR.mkdir(parents=True, exist_ok=True)
    reports: dict[str, str] = {}

    try:
        for name, instruction_path in AGENTS.items():
            output_path = ASSESSMENT_DIR / f"{name}.md"
            print(f"Running {name} agent...", flush=True)
            instructions = instruction_path.read_text(encoding="utf-8") + OUTPUT_INSTRUCTIONS
            run_codex(codex, instructions, output_path)
            reports[name] = output_path.read_text(encoding="utf-8")
            print(f"Saved {output_path.relative_to(ROOT)}", flush=True)

        backlog_path = ROOT / "backlog.md"
        print("Running lead agent...", flush=True)
        run_codex(codex, build_lead_prompt(reports), backlog_path)
        print(f"Saved {backlog_path.relative_to(ROOT)}", flush=True)
    except subprocess.CalledProcessError as error:
        print(
            f"Error: codex exec failed with exit code {error.returncode}.",
            file=sys.stderr,
        )
        return error.returncode or 1
    except OSError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    print("Assessment complete.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
