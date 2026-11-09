"""javascript / typescript: HTTP routes (Express, Koa-router, Fastify, Hono, Next.js files) and requests (fetch, axios,
HTTP clients, data fetching hooks, GraphQL operations).

Layers, each importing only the ones before it: syntax/ reads nodes, bindings/ what a file's names are bound to,
declarations/ how a call declares a route or mount, values/ resolves URL expressions, clients/ finds the HTTP clients
and their base paths, module.py puts one file's readers together (linker.py opens the files a module imports), routes/
and calls/ hold the collectors.
"""

from .extractor import JavaScriptExtractor

__all__ = ['JavaScriptExtractor']
