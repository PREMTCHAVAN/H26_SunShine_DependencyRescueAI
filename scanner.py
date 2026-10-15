from collections import defaultdict
from pathlib import Path
import tomllib

from packaging.requirements import Requirement, InvalidRequirement
from packaging.utils import canonicalize_name

REPO = Path(__file__).resolve().parent / "repos" / "LinkWatch"


def read_dependencies(repo):
    dependencies = defaultdict(list)

    def add_requirement(text, source):
        try:
            requirement = Requirement(text)
        except InvalidRequirement:
            print(f"Could not parse: {source}: {text}")
            return

        name = canonicalize_name(requirement.name)

        dependencies[name].append({
            "source": source,
            "requirement": requirement,
        })

    for filename in ("requirements.txt", "requirements-dev.txt"):
        path = repo / filename

        if not path.exists():
            continue

        for number, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), start=1
        ):
            line = line.strip()

            if line and not line.startswith("#"):
                add_requirement(line, f"{filename}:{number}")

    project_file = repo / "pyproject.toml"

    if project_file.exists():
        with project_file.open("rb") as file:
            data = tomllib.load(file)

        for text in data.get("project", {}).get("dependencies", []):
            add_requirement(text, "pyproject.toml [project.dependencies]")

    return dependencies


def show_findings(dependencies):
    print(f"\nFound {len(dependencies)} unique declared packages.")

    findings = 0

    for name, entries in sorted(dependencies.items()):
        # Compare declarations only under the same markers and extras.
        groups = defaultdict(list)

        for entry in entries:
            requirement = entry["requirement"]
            context = (
                str(requirement.marker or ""),
                tuple(sorted(requirement.extras)),
            )
            groups[context].append(entry)

        for entries_in_context in groups.values():
            constraints = {
                (
                    str(entry["requirement"].specifier),
                    entry["requirement"].url,
                )
                for entry in entries_in_context
            }

            if len(constraints) <= 1:
                continue

            findings += 1
            print(f"\nREVIEW: {name}")
            print("Different dependency constraints were found:")

            for entry in entries_in_context:
                print(
                    f"  {entry['source']} -> "
                    f"{entry['requirement']}"
                )

    if not findings:
        print("No differing constraints found in the scanned declarations.")

    print("\nThis check detects differences, not all dependency risks.")


if __name__ == "__main__":
    if not REPO.is_dir():
        raise SystemExit(f"Repository not found: {REPO}")

    dependencies = read_dependencies(REPO)
    show_findings(dependencies)