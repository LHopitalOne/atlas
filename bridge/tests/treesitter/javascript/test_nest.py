import unittest

from .support import Repository

MAIN = """
import { NestFactory } from '@nestjs/core';
async function bootstrap() {
  const app = await NestFactory.create(AppModule);
  app.setGlobalPrefix('api', { exclude: ['health', { path: 'metrics/(.*)', method: RequestMethod.GET }] });
  await app.listen(3000);
}
bootstrap();
"""
PEOPLE = """
import { Controller, Get, Post, Put, Delete, Param } from '@nestjs/common';

@Controller('people')
export class PersonController {
  @Get()
  getAllPeople() {}

  @Get(':id')
  @Authenticated()
  getPerson(@Param() { id }: Dto) {}

  @Put(':id/assets')
  updateAssets() {}

  @Delete(['', 'all'])
  deleteAll() {}

  helper() {}
}
"""
HEALTH = """
import { Controller, Get } from '@nestjs/common';
@Controller()
export class HealthController {
  @Get('health') health() {}
  @Get('metrics/cpu') cpu() {}
}
"""


def routes(files):
    return {(m, str(r.path)): r for r in Repository(files).extract().routes for m in r.methods}


class NestRoutesTest(unittest.TestCase):
    def test_controller_and_verb_paths_behind_the_global_prefix(self):
        found = routes({'src/main.ts': MAIN, 'src/people.controller.ts': PEOPLE})
        self.assertEqual(
            set(found),
            {
                ('GET', '/api/people'),
                ('GET', '/api/people/{id}'),
                ('PUT', '/api/people/{id}/assets'),
                ('DELETE', '/api/people'),
                ('DELETE', '/api/people/all'),
            },
        )
        route = found['GET', '/api/people/{id}']
        self.assertEqual(
            (route.file, route.line, route.handler), ('src/people.controller.ts', 9, 'PersonController.getPerson')
        )
        self.assertEqual(route.framework, 'nestjs')

    def test_excluded_routes_are_served_without_the_prefix(self):
        found = routes({'src/main.ts': MAIN, 'src/health.controller.ts': HEALTH})
        self.assertEqual(set(found), {('GET', '/health'), ('GET', '/metrics/cpu')})

    def test_an_exclude_entry_applies_to_its_method_and_its_wildcards(self):
        main = (
            "app.setGlobalPrefix('api', { exclude: [{ path: 'health', method: RequestMethod.POST }, 'hooks/*splat',"
            " 'pets/:petId'] });\n"
        )
        controller = (
            "import { Controller, Get, Post, Search } from '@nestjs/common';\n"
            "@Controller()\nclass C {\n  @Get('health') a() {}\n  @Post('health') b() {}\n"
            "  @Post('hooks/github/push') c() {}\n  @Get('pets/:id') d() {}\n  @Search('pets') e() {}\n}\n"
        )
        self.assertEqual(
            set(routes({'src/main.ts': main, 'src/c.ts': controller})),
            {
                ('GET', '/api/health'),
                ('POST', '/health'),
                ('POST', '/hooks/github/push'),
                ('GET', '/pets/{id}'),
                ('SEARCH', '/api/pets'),
            },
        )

    def test_without_a_global_prefix(self):
        self.assertIn(('GET', '/people/{id}'), routes({'src/people.controller.ts': PEOPLE}))

    def test_a_prefix_in_a_const_and_controller_options(self):
        files = {
            'src/main.ts': "const PREFIX = 'v2';\nfunction boot(app) { app.setGlobalPrefix(PREFIX); }\n",
            'src/cats.ts': (
                "import { Controller, Get } from '@nestjs/common';\n"
                "@Controller({ path: 'cats', host: 'x' })\nclass Cats { @Get(':id') one() {} }\n"
            ),
        }
        self.assertEqual(set(routes(files)), {('GET', '/v2/cats/{id}')})

    def test_applications_with_different_prefixes_get_none(self):
        files = {
            'a/main.ts': "app.setGlobalPrefix('api');\n",
            'b/main.ts': "app.setGlobalPrefix('internal');\n",
            'src/people.controller.ts': PEOPLE,
        }
        self.assertIn(('GET', '/people/{id}'), routes(files))

    def test_uri_versioning(self):
        controller = (
            "import { Controller, Get, Version } from '@nestjs/common';\n"
            "@Controller({ path: 'cats', version: '1' })\n"
            "class Cats {\n  @Get() all() {}\n  @Version('2')\n  @Get(':id') one() {}\n}\n"
        )
        versioning = 'app.enableVersioning({ type: VersioningType.URI });\n'
        self.assertEqual(
            set(routes({'src/main.ts': versioning, 'src/cats.ts': controller})),
            {('GET', '/v1/cats'), ('GET', '/v2/cats/{id}')},
        )
        self.assertEqual(set(routes({'src/cats.ts': controller})), {('GET', '/cats'), ('GET', '/cats/{id}')})

    def test_unknown_paths_and_other_libraries_declare_nothing(self):
        files = {
            'src/a.ts': "import { Controller, Get } from '@nestjs/common';\n"
            "@Controller(Keys.Asset)\nclass A { @Get('x') x() {} }\n",
            'src/b.ts': "import { Controller } from '@nestjs/common';\nimport { Get } from 'other';\n"
            "@Controller('b')\nclass B { @Get('y') y() {} }\n",
            'src/c.ts': "import { Controller, Get } from '@nestjs/common';\n"
            "@Controller('c')\nclass C { @Get(path) z() {} }\n",
        }
        self.assertEqual(routes(files), {})

    def test_test_files_declare_nothing(self):
        self.assertEqual(routes({'src/people.controller.spec.ts': PEOPLE}), {})


if __name__ == '__main__':
    unittest.main()
