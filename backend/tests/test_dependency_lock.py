from importlib.metadata import metadata
from pathlib import Path

from packaging.requirements import Requirement
from packaging.version import Version


BACKEND_DIR = Path(__file__).resolve().parents[1]


def _requirement(path: Path, package: str) -> Requirement:
    for line in path.read_text().splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            requirement = Requirement(stripped)
            if requirement.name.lower() == package.lower():
                return requirement
    raise AssertionError(f"{package} is missing from {path.name}")


def test_urllib3_lock_is_fixed_and_compatible_with_botocore() -> None:
    declared = _requirement(BACKEND_DIR / "requirements.txt", "urllib3")
    locked_urllib3 = _requirement(BACKEND_DIR / "requirements.lock", "urllib3")
    locked_botocore = _requirement(BACKEND_DIR / "requirements.lock", "botocore")

    assert str(declared.specifier) == "<3,>=2.8"
    urllib3_pin = list(locked_urllib3.specifier)
    botocore_pin = list(locked_botocore.specifier)
    assert len(urllib3_pin) == 1 and urllib3_pin[0].operator == "=="
    assert len(botocore_pin) == 1 and botocore_pin[0].operator == "=="

    botocore_urllib3 = next(
        Requirement(value)
        for value in metadata("botocore").get_all("Requires-Dist", [])
        if Requirement(value).name.lower() == "urllib3"
    )
    urllib3_version = Version(urllib3_pin[0].version)

    assert urllib3_version >= Version("2.8.0")
    assert declared.specifier.contains(urllib3_version, prereleases=False)
    assert botocore_urllib3.specifier.contains(urllib3_version, prereleases=False)
