"""javascript / typescript: HTTP routes (Express, Koa-router, Fastify, Hono) and requests (fetch, axios, HTTP clients).

Layers, each importing only the ones before it: syntax/ reads nodes, bindings/ what a file's names are bound to,
declarations/ how a call declares a route or mount, values/ resolves URL expressions, clients/ finds the HTTP clients
and their base paths, module.py puts one file's readers together, routes/ and calls/ hold the collectors.
"""

from .extractor import JavaScriptExtractor

__all__ = ['JavaScriptExtractor']
