"""Which Rust files are test or tooling code, from their path alone."""

import re

from ..kit import TestPathPolicy


class RustTestPolicy(TestPathPolicy):
    """The shared conventions plus crates and folders named as test helpers: 'server-test', 'mocks', 'test_utils'."""

    TEST_DIR = re.compile(r'(^|[-_])(tests?|testutils|mocks?)($|[-_])')  # a folder with 'test' or 'mock' as a word

    def is_test(self, path: str) -> bool:
        dirs = path.replace('\\', '/').split('/')[:-1]
        return super().is_test(path) or any(self.TEST_DIR.search(d) for d in dirs)
