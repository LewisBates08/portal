"""Fail if actual environment files exist in the index or reachable Git history.

Templates ending in .example are intentionally permitted. No secret contents are printed.
This cannot establish the contents of deleted remote branches or other clones.
"""

from pathlib import PurePosixPath
import subprocess
import sys


def actual_environment_file(path):
    name = PurePosixPath(path).name.lower()
    if name.endswith(".example"):
        return False
    return (
        name == ".env"
        or name.startswith(".env.")
        or name.endswith(".env")
        or ".env." in name
    )


def git(*args):
    return subprocess.check_output(["git", *args], text=True)


def main():
    indexed = git("ls-files", "-z").split("\0")
    historical = git(
        "log", "--all", "--format=", "--name-only", "--diff-filter=ACMR"
    ).splitlines()
    bad = sorted({p for p in indexed + historical if p and actual_environment_file(p)})
    if bad:
        print("FAIL: actual environment-file paths found (contents withheld):")
        print("\n".join(bad))
        return 1
    print(
        "PASS: no actual .env files in the index or reachable history; only templates are permitted."
    )
    if git("rev-parse", "--is-shallow-repository").strip() == "true":
        print("FAIL: a shallow clone cannot verify full reachable history.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
