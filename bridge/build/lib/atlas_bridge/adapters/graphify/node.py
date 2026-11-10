"""One Graphify node (a dict in graph.json's node-link data), read through methods instead of raw keys."""

import posixpath
import re
from collections import Counter

from ...core.model import Community, Kind


class GraphifyNode:
    LOCATION = re.compile(r'L(\d+)')  # Graphify's source_location, 'L42'

    def __init__(self, data: dict):
        self.data = data

    @property
    def id(self):
        return self.data['id']

    @property
    def label(self):
        return self.data.get('label', '')

    @property
    def source_file(self):
        return self.data.get('source_file') or ''

    @property
    def repo(self):
        return self.data.get('repo') or ''

    @property
    def line(self):
        m = self.LOCATION.match(self.data.get('source_location') or '')
        return int(m.group(1)) if m else 0

    @property
    def is_file(self):
        """A file node stands for the file itself: its label is the file's name."""
        return not self.data.get('_callable') and self.label == posixpath.basename(self.source_file)

    @property
    def kind(self):
        if self.data.get('_callable_class'):
            return Kind.CLASS
        return Kind.FUNCTION if self.data.get('_callable') else Kind.OTHER

    @staticmethod
    def majority_community(nodes):
        """The community most of these nodes belong to; ties go to the lowest community id."""
        votes = Counter(
            (n.data['community'], n.data.get('community_name') or '') for n in nodes if 'community' in n.data
        )
        if not votes:
            return None
        (cid, name), _ = min(votes.items(), key=lambda kv: (-kv[1], kv[0][0]))
        return Community(cid, name)
