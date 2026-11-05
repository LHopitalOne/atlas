"""Which Python files are test or tooling code, from their path alone."""

from ..kit import TestPathPolicy


class PythonTestPolicy(TestPathPolicy):
    """The kit's test conventions, plus CI scripts anywhere and developer tooling at the repository root."""

    TOOLING_DIRS = frozenset({'.github', '.circleci', '.buildkite', '.gitlab'})  # CI scripts, anywhere in the path
    TOOLING_ROOTS = frozenset({'bin', 'devenv', 'scripts', 'tools'})  # developer tooling at the repository root

    def is_test(self, path: str) -> bool:
        return super().is_test(path) or self.is_tooling(path)

    def is_tooling(self, path: str) -> bool:
        parts = path.replace('\\', '/').split('/')[:-1]
        return bool(parts) and (parts[0] in self.TOOLING_ROOTS or any(p in self.TOOLING_DIRS for p in parts))
