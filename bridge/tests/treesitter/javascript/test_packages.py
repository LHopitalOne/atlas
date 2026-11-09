import json
import os
import tempfile
import unittest

from atlas_bridge.adapters.treesitter.javascript import JavaScriptExtractor
from atlas_bridge.adapters.treesitter.javascript.packages.globs import FolderGlobs
from atlas_bridge.adapters.treesitter.javascript.packages.monorepo import Monorepo, WorkspaceFiles
from atlas_bridge.adapters.treesitter.javascript.packages.package import CompilerFolders, PackageEntry
from atlas_bridge.adapters.treesitter.kit import RepositoryFiles

from .support import Repository

GENERATED = """
import * as Oazapfts from "@oazapfts/runtime";
import * as QS from "@oazapfts/runtime/query";
export const defaults: Oazapfts.Defaults<Oazapfts.CustomHeaders> = { headers: {}, baseUrl: "/api" };
const oazapfts = Oazapfts.runtime(defaults);
export function listPets({ kind }: { kind?: string } = {}, opts?: Oazapfts.RequestOpts) {
    return oazapfts.ok(oazapfts.fetchJson<{ status: 200 }>(`/pets${QS.query(QS.explode({ kind }))}`, { ...opts }));
}
export function getPet({ id }: { id: string }, opts?: Oazapfts.RequestOpts) {
    return oazapfts.ok(oazapfts.fetchJson<{ status: 200 }>(`/pets/${encodeURIComponent(id)}`, { ...opts }));
}
export function updatePet({ id, pet }: { id: string; pet: Pet }, opts?: Oazapfts.RequestOpts) {
    return oazapfts.ok(oazapfts.fetchJson(`/pets/${encodeURIComponent(id)}`, oazapfts.json({
        ...opts, method: "PUT", body: pet
    })));
}
export function deletePet({ id }: { id: string }, opts?: Oazapfts.RequestOpts) {
    return oazapfts.ok(oazapfts.fetchText(`/pets/${encodeURIComponent(id)}`, { ...opts, method: "DELETE" }));
}
"""
WEB = """
import { getPet, updatePet, deletePet, listPets } from '@acme/sdk';
import { useMutation } from './query';

export async function show(petId: string) {
  const pet = await getPet({ id: petId });
  return updatePet({ id: petId, pet });
}
export const all = () => listPets();
export const remove = () => useMutation(deletePet, { onSuccess: () => {} });
export const options = { mutationFn: deletePet };
"""
FETCHING = """
export const getUser = (id: string) => fetch(`/api/users/${id}`);
export function ping() { return fetch('/api/ping', { method: 'POST' }); }
"""


class Monorepo_:
    """{path: text} written under a temporary folder; the calls JavaScriptExtractor finds in one of its folders."""

    def __init__(self, files):
        self._files = files

    def calls(self, repo_folder):
        with tempfile.TemporaryDirectory() as root:
            for path, text in self._files.items():
                full = os.path.join(root, path)
                os.makedirs(os.path.dirname(full), exist_ok=True)
                with open(full, 'w') as f:
                    f.write(text)
            files = RepositoryFiles(os.path.join(root, repo_folder))
            extractor = JavaScriptExtractor()
            out = extractor.extract('web', files, [p for p in files.paths() if extractor.handles(p)])
            return {(c.method, str(c.path), c.file, c.line) for c in out.calls}


SDK = {
    'pnpm-workspace.yaml': "packages:\n  - 'packages/*'\n  - apps/*  # the apps\nallowBuilds:\n  x: true\n",
    'packages/sdk/package.json': '{"name": "@acme/sdk", "main": "./build/index.js"}',
    'packages/sdk/src/index.ts': "export * from './client.js';\nexport { helper } from './helper';\n",
    'packages/sdk/src/client.ts': GENERATED,
    'apps/web/package.json': '{"name": "web", "dependencies": {"@acme/sdk": "workspace:*"}}',
    'apps/web/src/pets.ts': WEB,
}


class GeneratedClientTest(unittest.TestCase):
    def test_runtime_requests_behind_the_defaults_base_url(self):
        found = {(c.method, str(c.path), c.line) for c in Repository({'src/client.ts': GENERATED}).extract().calls}
        self.assertEqual(found, {('GET', '/api/pets', 7)})  # the others wait for their callers' ids

    def test_a_generated_function_is_settled_at_its_callers_in_the_same_repository(self):
        caller = "import { getPet } from './client';\nexport const one = (petId) => getPet({ id: petId });\n"
        found = Repository({'src/client.ts': GENERATED, 'src/one.ts': caller}).extract().calls
        self.assertIn(
            ('GET', '/api/pets/{petId}', 'src/one.ts', 2), {(c.method, str(c.path), c.file, c.line) for c in found}
        )


class WorkspacePackageTest(unittest.TestCase):
    def test_package_functions_are_reported_where_the_app_calls_them(self):
        found = Monorepo_(SDK).calls('apps/web')
        self.assertEqual(
            found,
            {
                ('GET', '/api/pets/{petId}', 'src/pets.ts', 6),
                ('PUT', '/api/pets/{petId}', 'src/pets.ts', 7),
                ('GET', '/api/pets', 'src/pets.ts', 9),
                ('DELETE', '/api/pets/{id}', 'src/pets.ts', 10),  # handed on: its id is filled in later
                ('DELETE', '/api/pets/{id}', 'src/pets.ts', 11),
            },
        )

    def test_npm_workspaces_and_plain_fetch_wrappers(self):
        files = {
            'package.json': '{"name": "root", "workspaces": {"packages": ["libs/**"]}}',
            'libs/net/api/package.json': '{"name": "@acme/api", "exports": {".": {"import": "./dist/index.mjs"}}}',
            'libs/net/api/src/index.ts': FETCHING,
            'web/app.ts': (
                "import { getUser, ping } from '@acme/api';\nexport const u = (uid) => getUser(uid);\nping();\n"
            ),
        }
        self.assertEqual(
            Monorepo_(files).calls('web'),
            {('GET', '/api/users/{uid}', 'app.ts', 2), ('POST', '/api/ping', 'app.ts', 3)},
        )

    def test_names_not_imported_from_the_package_are_not_followed(self):
        files = dict(SDK)
        files['apps/web/src/pets.ts'] = (
            "import { getPet } from 'some-other-sdk';\nconst listPets = () => [];\n"
            'export const a = () => getPet({ id: 1 });\n'
            'export const b = () => listPets();\n'
        )
        self.assertEqual(Monorepo_(files).calls('apps/web'), set())

    def test_without_a_workspace_nothing_is_followed(self):
        files = {k: v for k, v in SDK.items() if k != 'pnpm-workspace.yaml'}
        self.assertEqual(Monorepo_(files).calls('apps/web'), set())


class WorkspaceLayoutTest(unittest.TestCase):
    def test_pnpm_and_npm_workspace_globs(self):
        with tempfile.TemporaryDirectory() as root:
            for folder in ('packages/a', 'packages/deep/b', 'packages/node_modules/c', 'docs', 'packages/test'):
                os.makedirs(os.path.join(root, folder))
                with open(os.path.join(root, folder, 'package.json'), 'w') as f:
                    f.write(json.dumps({'name': folder.rsplit('/', 1)[-1]}))
            with open(os.path.join(root, 'pnpm-workspace.yaml'), 'w') as f:
                f.write("packages: ['packages/**', docs, '!packages/test']\n")
            self.assertEqual(WorkspaceFiles.patterns(root), ['packages/**', 'docs', '!packages/test'])
            found = FolderGlobs(root).expand(WorkspaceFiles.patterns(root))
            self.assertEqual(
                [os.path.relpath(f, root) for f in found],
                ['docs', 'packages', 'packages/a', 'packages/deep', 'packages/deep/b'],
            )
            self.assertEqual(sorted(Monorepo.around(os.path.join(root, 'docs')).packages()), ['a', 'b', 'docs'])

    def test_package_entry_candidates(self):
        self.assertEqual(PackageEntry.candidates({'main': './build/index.js'})[:2], ['./src/index', './build/index.js'])
        types = PackageEntry.candidates({'exports': {'.': {'types': './dist/index.d.ts'}}})
        self.assertEqual(types[0], './src/index')
        self.assertEqual(PackageEntry.candidates({}, 'client'), ['./client', './src/client'])

    def test_package_entry_follows_the_tsconfig_folders_and_exports_subpaths(self):
        compiled = ('lib', 'source')
        self.assertEqual(PackageEntry.candidates({'main': './lib/index.js'}, '', compiled)[0], './source/index')
        exports = {'exports': {'.': './dist/index.js', './client': {'import': './dist/client.mjs'}}}
        self.assertEqual(PackageEntry.candidates(exports, 'client')[:2], ['./src/client', './dist/client.mjs'])
        with tempfile.TemporaryDirectory() as root:
            with open(os.path.join(root, 'tsconfig.json'), 'w') as f:
                f.write('{\n  // built by tsc\n  "compilerOptions": { "outDir": "./out/", "rootDir": "lib", },\n}\n')
            self.assertEqual(CompilerFolders.of(root), ('out', 'lib'))


if __name__ == '__main__':
    unittest.main()
