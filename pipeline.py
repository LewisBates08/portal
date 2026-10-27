#!/usr/bin/env python3
"""Run the delivery pipeline with non-interactive Codex agents."""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
AGENTS_DIR = ROOT / "agents"
PIPELINE_DIR = ROOT / "pipeline"

DELIVERY_AGENTS = (
    ("planner", AGENTS_DIR / "planner.md"),
    ("developer", AGENTS_DIR / "developer.md"),
    ("delivery-tester", AGENTS_DIR / "tester_agent.md"),
)
REVIEWER = AGENTS_DIR / "reviewer.md"

WRITE_SCOPE_NOTE = """\

Orchestration note: you may create, edit, or delete files only inside the project
root shown as your working directory. Follow your role-specific limits as well.
Complete this stage before returning your final response.
"""

REVIEW_OUTPUT_NOTE = """\

Orchestration note: work in read-only mode and do not create or edit files.
Return the complete Markdown review as your final answer, beginning with exactly
APPROVED or REJECTED. The orchestration script will save it to pipeline/review.md.
"""

REPOSITORY_PATHS_NOTE = """\

Repository path guidance: the root instructions are in AGENTS.md. Assessment
reports are in assessment/ (singular). The delivery plan, test results, and
review are in pipeline/spec.md, pipeline/test-results.md, and pipeline/review.md.
Use these current paths if the role instructions contain older or misspelled paths.
"""

STAGE_NOTES = {
    "planner": """\
For this stage, update pipeline/spec.md additively. Preserve its existing roadmap
and scope the immediate delivery work to the user's requested task, if supplied.
Do not write code.
""",
    "developer": """\
Implement the immediate task described in pipeline/spec.md and the run context.
Keep changes within that scope and within the project root.
""",
    "delivery-tester": """\
Test the changes in the current spec and write the outcomes to
pipeline/test-results.md. Do not change application code.
""",
    "reviewer": """\
Review pipeline/spec.md, pipeline/test-results.md, and the current git diff.
Report whether the specified work is supported by the available evidence.
""",
}


def run_codex(
    codex: str,
    prompt: str,
    sandbox: str,
    output_path: Path | None = None,
) -> None:
    """Run one Codex stage in the requested sandbox."""
    command = [
        codex,
        "exec",
        "--sandbox",
        sandbox,
        "--cd",
        str(ROOT),
        "--ephemeral",
        "--color",
        "never",
    ]
    if output_path is not None:
        command.extend(("--output-last-message", str(output_path)))
    command.append("-")
    subprocess.run(command, input=prompt, text=True, check=True)


def build_stage_prompt(name: str, instruction_path: Path, task: str | None) -> str:
    prompt = instruction_path.read_text(encoding="utf-8")
    prompt += "\n\n" + REPOSITORY_PATHS_NOTE + "\n\n" + STAGE_NOTES[name]
    if task:
        prompt += f"\nRun-specific task from the user:\n{task.strip()}\n"
    if name == "reviewer":
        prompt += REVIEW_OUTPUT_NOTE
    else:
        prompt += WRITE_SCOPE_NOTE
    return prompt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--task",
        help="Scope this pipeline run to a specific user-requested task.",
    )
    args = parser.parse_args()

    codex = shutil.which("codex")
    if codex is None:
        print("Error: codex CLI was not found on PATH.", file=sys.stderr)
        return 1

    instruction_paths = [path for _, path in DELIVERY_AGENTS] + [REVIEWER]
    missing = [
        str(path.relative_to(ROOT)) for path in instruction_paths if not path.is_file()
    ]
    if missing:
        print(
            f"Error: missing agent instruction file(s): {', '.join(missing)}",
            file=sys.stderr,
        )
        return 1

    PIPELINE_DIR.mkdir(parents=True, exist_ok=True)

    try:
        for name, instruction_path in DELIVERY_AGENTS:
            print(f"Running {name} agent...", flush=True)
            prompt = build_stage_prompt(name, instruction_path, args.task)
            run_codex(codex, prompt, sandbox="workspace-write")
            print(f"Completed {name} agent.", flush=True)

        review_path = PIPELINE_DIR / "review.md"
        print("Running reviewer agent...", flush=True)
        # Never let a previous run's decision determine this run's status.
        review_path.write_text("", encoding="utf-8")
        reviewer_prompt = build_stage_prompt("reviewer", REVIEWER, args.task)
        run_codex(
            codex,
            reviewer_prompt,
            sandbox="read-only",
            output_path=review_path,
        )
        print(f"Saved {review_path.relative_to(ROOT)}", flush=True)
        review = review_path.read_text(encoding="utf-8").lstrip()
        first_line = review.splitlines()[0].strip() if review else ""
        match = re.match(r"^(APPROVED|REJECTED)(?:\b|$)", first_line)
        decision = match.group(1) if match else ""
        if decision != "APPROVED":
            if decision == "REJECTED":
                print(
                    "Reviewer rejected the delivery; failing the pipeline.",
                    file=sys.stderr,
                )
            else:
                print(
                    "Error: reviewer output must begin with APPROVED or REJECTED; "
                    "failing closed.",
                    file=sys.stderr,
                )
            return 1
    except subprocess.CalledProcessError as error:
        print(
            f"Error: codex exec failed with exit code {error.returncode}.",
            file=sys.stderr,
        )
        return error.returncode or 1
    except OSError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    print("Delivery pipeline complete.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
