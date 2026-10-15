import json
from datetime import datetime, timezone
from pathlib import Path

from packaging.utils import canonicalize_name

from scanner import REPO, read_dependencies
from usage_scanner import find_imports
from call_scanner import find_calls
from dependency_usage import IMPORT_HINTS


def matching_modules(package, imports):
    return {
        module
        for module in imports
        if canonicalize_name(module) == package
        or module in IMPORT_HINTS.get(package, set())
    }


def build_evidence(repo):
    dependencies = read_dependencies(repo)
    imports = find_imports(repo)
    calls = find_calls(repo)

    evidence = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "repository": str(repo),
        "analysis_type": "static inspection",
        "tests_executed": False,
        "limitations": [
            "Import-to-package mappings are preliminary.",
            "Calls are candidates; scope and reassignment are not resolved.",
            "Instance methods and dynamic imports are not traced.",
            "Package maintenance metadata has not been collected.",
            "Skipped or unsupported inputs are printed to the terminal.",
        ],
        "dependencies": [],
    }

    for package, declarations in sorted(dependencies.items()):
        modules = matching_modules(package, imports)

        evidence["dependencies"].append({
            "package": package,
            "declarations": [
                {
                    "source": entry["source"],
                    "requirement": str(entry["requirement"]),
                }
                for entry in declarations
            ],
            "candidate_import_modules": sorted(modules),
            "import_locations": [
                location
                for module in sorted(modules)
                for location in imports[module]
            ],
            "candidate_calls": [
                call
                for call in calls
                if call["candidate_target"].split(".")[0] in modules
            ],
        })

    return evidence


if __name__ == "__main__":
    if not REPO.is_dir():
        raise SystemExit(f"Repository not found: {REPO}")

    evidence = build_evidence(REPO)

    output_dir = Path(__file__).resolve().parent / "outputs"
    output_dir.mkdir(exist_ok=True)

    output_file = output_dir / "scan_evidence.json"
    output_file.write_text(
        json.dumps(evidence, indent=2),
        encoding="utf-8",
    )

    print(f"Saved evidence: {output_file}")
    print(f"Dependencies recorded: {len(evidence['dependencies'])}")