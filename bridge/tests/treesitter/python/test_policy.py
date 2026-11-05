import unittest

from atlas_bridge.adapters.treesitter.python.policy import PythonTestPolicy


class PythonTestPolicyTest(unittest.TestCase):
    def test_tests_ci_scripts_and_root_tooling(self):
        policy = PythonTestPolicy()
        self.assertTrue(policy.is_test('tests/test_api.py'))
        self.assertTrue(policy.is_test('pkg/conftest.py'))
        self.assertTrue(policy.is_test('.github/workflows/scripts/bootstrap.py'))
        self.assertTrue(policy.is_test('a/.circleci/run.py'))
        self.assertTrue(policy.is_test('bin/tool.py'))
        self.assertTrue(policy.is_test('scripts\\deploy.py'))
        self.assertFalse(policy.is_test('pkg/bin/run.py'))
        self.assertFalse(policy.is_test('setup.py'))
        self.assertFalse(policy.is_test('src/app/views.py'))
