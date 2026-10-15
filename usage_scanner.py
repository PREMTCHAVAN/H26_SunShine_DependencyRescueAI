import ast
from pathlib import Path

REPO = Path(__file__).resolve().parent / "repos" / "LinkWatch"

SKIP_DIRS = {
    ".git", ".venv", "venv", "__pycache__",
    "node_modules", "build", "dist",
}


def find_imports(repo):
    usages = {}

    for path in sorted(repo.rglob("*.py")):
        relative_path = path.relative_to(repo)

        if any(part in SKIP_DIRS for part in relative_path.parts):
            continue

        try:
            source = path.read_text(encoding="utf-8-sig")
            tree = ast.parse(source, filename=str(path))
        except (OSError, UnicodeError, SyntaxError) as error:
            print(f"Skipped {relative_path}: {error}")
            continue

        for node in ast.walk(tree):
            imports = []

            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append((
                        alias.name.split(".")[0],
                        alias.asname or alias.name,
                    ))

            elif isinstance(node, ast.ImportFrom):
                # Relative imports refer to this project's own code.
                if node.level or not node.module:
                    continue

                module = node.module.split(".")[0]

                for alias in node.names:
                    imports.append((
                        module,
                        alias.asname or alias.name,
                    ))

            for module, local_name in imports:
                usages.setdefault(module, []).append({
                    "file": relative_path.as_posix(),
                    "line": node.lineno,
                    "local_name": local_name,
                    "statement": ast.get_source_segment(source, node),
                })

    return usages


if __name__ == "__main__":
    if not REPO.is_dir():
        raise SystemExit(f"Repository not found: {REPO}")

    for module, locations in sorted(find_imports(REPO).items()):
        print(f"\n{module}")

        for location in locations:
            print(f"  {location['file']}:{location['line']}")
            print(f"    {location['statement']}")