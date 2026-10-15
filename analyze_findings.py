import json
from collections import defaultdict
from pathlib import Path

from packaging.requirements import Requirement

ROOT = Path(__file__).resolve().parent
INPUT = ROOT / "outputs" / "scan_evidence.json"
OUTPUT = ROOT / "outputs" / "scan_findings.json"


def analyze(evidence):
    findings = []

    for dependency in evidence["dependencies"]:
        groups = defaultdict(list)

        for declaration in dependency["declarations"]:
            requirement = Requirement(declaration["requirement"])

            # Compare declarations with the same conditions and extras.
            context = (
                str(requirement.marker or ""),
                tuple(sorted(requirement.extras)),
            )

            groups[context].append((requirement, declaration))

        for (marker, extras), entries in groups.items():
            constraints = {
                (str(requirement.specifier), requirement.url)
                for requirement, _ in entries
            }

            if len(constraints) <= 1:
                continue

            findings.append({
                "package": dependency["package"],
                "category": "declaration_difference",
                "status": "needs_review",
                "evidence_type": "observed_static",
                "summary": (
                    "Different dependency constraints were found "
                    "under the same marker and extras."
                ),
                "marker": marker,
                "extras": list(extras),
                "declarations": [
                    declaration for _, declaration in entries
                ],
                "import_locations": dependency["import_locations"],
                "limitation": (
                    "Different constraints may overlap or be intentional. "
                    "This finding does not prove incompatibility."
                ),
            })

    return findings


if __name__ == "__main__":
    if not INPUT.exists():
        raise SystemExit("Run python build_evidence.py first.")

    evidence = json.loads(INPUT.read_text(encoding="utf-8"))
    findings = analyze(evidence)

    result = {
        "evidence": evidence,
        "findings": findings,
        "ai_analysis_performed": False,
        "tests_executed": False,
    }

    OUTPUT.write_text(
        json.dumps(result, indent=2),
        encoding="utf-8",
    )

    print(f"Findings: {len(findings)}")

    for finding in findings:
        print(f"\nREVIEW: {finding['package']}")
        for declaration in finding["declarations"]:
            print(
                f"  {declaration['source']}"
                f" -> {declaration['requirement']}"
            )

    print(f"\nSaved: {OUTPUT}")