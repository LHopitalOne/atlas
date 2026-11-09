"""GraphqlTransport: the HTTP request that carries a GraphQL document is reported as GraphQL, not as a POST."""

from ..base import RequestCollector
from .transport import GraphqlBody


class GraphqlTransport(RequestCollector):
    """Claims the requests that post a GraphQL document (GraphqlBody) before the HTTP idioms do, and sends nothing:
    GraphqlCalls reports each root field of the document instead of one POST to the endpoint."""

    NAMES = GraphqlBody.NAMES

    def claims(self, module, site):
        return super().claims(module, site) and GraphqlBody.sends_graphql(module, site)

    def requests(self, builder, site):
        return []
