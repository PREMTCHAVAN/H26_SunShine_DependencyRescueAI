from packaging.utils import canonicalize_name

from scanner import REPO, read_dependencies
from usage_scanner import find_imports

# Explicit mappings for packages whose import names differ.
# These are mapping hints, not dependency-risk findings.
IMPORT_HINTS = {
    "python-dateutil": {"dateutil"},
    "setuptools": {"setuptools", "pkg_resources"},
}


def show_dependency_usage(repo):
    dependencies = read_dependencies(repo)
    imports = find_imports(repo)

    for package, declarations in sorted(dependencies.items()):
        print(f"\nDEPENDENCY: {package}")

        for declaration in declarations:
            print(
                f"  Declared: {declaration['requirement']}"
                f" ({declaration['source']})"
            )

        matches = []

        for module, locations in imports.items():
            if module in IMPORT_HINTS.get(package, set()):
                mapping_method = "explicit mapping hint"
            elif canonicalize_name(module) == package:
                mapping_method = "package/import name match"
            else:
                continue

            for location in locations:
                matches.append((location, mapping_method))

        if not matches:
            print("  No matching direct imports found.")
            continue

        print("  Import locations:")

        for location, mapping_method in matches:
            print(f"    {location['file']}:{location['line']}")
            print(f"      {location['statement']}")
            print(f"      Mapping: {mapping_method}")


if __name__ == "__main__":
    if not REPO.is_dir():
        raise SystemExit(f"Repository not found: {REPO}")

    show_dependency_usage(REPO)