import unittest

from atlas_bridge.core.evidence import Assumption

from .support import RustRepo

SOURCE = """
impl UpstreamQuery for GetProjectStates {
    fn method(&self) -> Method { Method::POST }
    fn path(&self) -> Cow<'static, str> { Cow::Borrowed("/api/0/relays/projectconfigs/") }
}
"""


class RustAssumptionsTest(unittest.TestCase):
    def test_the_request_trait_is_matched_by_name(self):
        calls = RustRepo({'src/upstream.rs': SOURCE}).extract().calls
        self.assertEqual([c.assumptions for c in calls], [(Assumption('src/upstream.rs', 2, 'UpstreamQuery'),)])


if __name__ == '__main__':
    unittest.main()
