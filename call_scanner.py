import ast

from scanner import REPO
from usage_scanner import SKIP_DIRS


def dotted_name(node):
    if isinstance(node, ast.Name):
        return node.id

    if isinstance(node, ast.Attribute):
        parent = dotted_name(node.value)
        if parent:
            return f"{parent}.{node.attr}"

    return None


def find_calls(repo):
    results = []

    for path in sorted(repo.rglob("*.py")):
        relative = path.relative_to(repo)

        if any(part in SKIP_DIRS for part in relative.parts):
            continue

        try:
            source = path.read_text(encoding="utf-8-sig")
            tree = ast.parse(source, filename=str(path))
        except (OSError, UnicodeError, SyntaxError) as error:
            print(f"Skipped {relative}: {error}")
            continue

        # Collect possible targets for each imported name.
        aliases = {}

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for item in node.names:
                    local = item.asname or item.name.split(".")[0]
                    target = item.name if item.asname else local
                    aliases.setdefault(local, set()).add(target)

            elif isinstance(node, ast.ImportFrom):
                if node.level or not node.module:
                    continue

                for item in node.names:
                    if item.name == "*":
                        continue

                    local = item.asname or item.name
                    target = f"{node.module}.{item.name}"
                    aliases.setdefault(local, set()).add(target)

        class CallVisitor(ast.NodeVisitor):
            def __init__(self):
                self.context = []

            def visit_FunctionDef(self, node):
                self.context.append(node.name)
                self.generic_visit(node)
                self.context.pop()

            visit_AsyncFunctionDef = visit_FunctionDef

            def visit_ClassDef(self, node):
                self.context.append(node.name)
                self.generic_visit(node)
                self.context.pop()

            def visit_Call(self, node):
                called = dotted_name(node.func)

                if called:
                    root, separator, suffix = called.partition(".")

                    for target in sorted(aliases.get(root, set())):
                        resolved = (
                            f"{target}.{suffix}" if separator else target
                        )

                        results.append({
                            "file": relative.as_posix(),
                            "line": node.lineno,
                            "context": ".".join(self.context) or "<module>",
                            "written_call": called,
                            "candidate_target": resolved,
                        })

                self.generic_visit(node)

        CallVisitor().visit(tree)

    return results


if __name__ == "__main__":
    if not REPO.is_dir():
        raise SystemExit(f"Repository not found: {REPO}")

    for result in find_calls(REPO):
        print(f"\n{result['file']}:{result['line']}")
        print(f"  Context: {result['context']}")
        print(f"  Written call: {result['written_call']}")
        print(f"  Candidate target: {result['candidate_target']}")