"""JavaScriptExtractor: HTTP routes and requests of javascript, typescript and tsx files."""

from ..kit import LanguageExtractor
from .calls.composite import RequestCalls
from .channels.collector import ChannelCollector
from .collector import SharedPass
from .policy import JavaScriptTestPolicy
from .routes.express import ExpressRoutes
from .workspace import JavaScriptWorkspace


class JavaScriptExtractor(LanguageExtractor):
    """Routes: Express, Koa-router, Fastify and Hono, with the prefixes of `app.use('/prefix', router)` across files.

    Requests: `fetch(url, {method})`, `axios(config)`, `axios.get(url)`, `<client>.get/post/...(url)`,
    `<client>.request(config)`. URLs are resolved from string and template literals, `+` concatenation and const/let
    bindings in the enclosing function or module. A client's base path is prepended to the request path: the
    `baseURL`/`baseUrl`/`prefixUrl` given where it is made (`axios.create({baseURL})`, `new Client({baseUrl})`), or
    the default of a client class of the repository (`this.baseUrl = options.baseUrl ?? '/api/0'`), reached through
    `new Client()`, a parameter typed `Client`, a function that returns `new Client()`, or a module-level client.
    """

    GRAMMARS = frozenset({'javascript', 'typescript', 'tsx'})
    POLICY = JavaScriptTestPolicy

    def workspace(self, repo, sources) -> JavaScriptWorkspace:
        return JavaScriptWorkspace(repo, sources, self.POLICY())

    def collectors(self, workspace) -> list:
        shared = SharedPass(workspace, (ExpressRoutes(workspace), RequestCalls(workspace)))  # one parse per file
        return [shared, ChannelCollector(workspace)]
