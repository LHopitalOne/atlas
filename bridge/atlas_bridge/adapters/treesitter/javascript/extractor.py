"""JavaScriptExtractor: HTTP routes and requests of javascript, typescript and tsx files."""

from ..kit import LanguageExtractor
from .calls.composite import RequestCalls
from .calls.graphql.collector import GraphqlCalls
from .calls.keyed import KeyedRequests
from .channels.collector import ChannelCollector
from .collector import SharedPass
from .policy import JavaScriptTestPolicy
from .routes.express import ExpressRoutes
from .routes.nextjs import NextRoutes
from .workspace import JavaScriptWorkspace


class JavaScriptExtractor(LanguageExtractor):
    """Routes: Express, Koa-router, Fastify and Hono, with the prefixes of `app.use('/prefix', router)` across files;
    Next.js API routes named by their files (`pages/api/`, `app/**/route.ts`).

    Requests: `fetch(url, {method})`, `axios(config)`, `axios.get(url)`, `<client>.get/post/...(url)`,
    `<client>.request(config)`, and the keys of data fetching hooks (`useSWR('/api/notes')`). URLs are resolved from
    string and template literals, `+` concatenation, const/let bindings in the enclosing function or module, and
    members of object literals reached through destructuring and imports. A client's base path is prepended to the
    request path: the `baseURL`/`baseUrl`/`prefixUrl` given where it is made (`axios.create({baseURL})`,
    `new Client({baseUrl})`), or the default of a client class of the repository (`this.baseUrl = options.baseUrl ??
    '/api/0'`), reached through `new Client()`, a parameter typed `Client`, a function that returns `new Client()`, or
    a module-level client. GraphQL operations, posted as `{ query }` or given to a GraphQL client, are one GRAPHQL call
    per root field.
    """

    GRAMMARS = frozenset({'javascript', 'typescript', 'tsx'})
    POLICY = JavaScriptTestPolicy

    def workspace(self, repo, sources) -> JavaScriptWorkspace:
        return JavaScriptWorkspace(repo, sources, self.POLICY())

    def collectors(self, workspace) -> list:
        shared = (ExpressRoutes(workspace), RequestCalls(workspace), KeyedRequests(workspace), GraphqlCalls(workspace))
        # one parse per file for the shared pass; Next.js routes and other protocols read the files they pick
        return [SharedPass(workspace, shared), NextRoutes(workspace), ChannelCollector(workspace)]
