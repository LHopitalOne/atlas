import unittest

from .support import Repository

SDK = """
import { client } from './client.gen';

export const listPets = (options?: Options<ListPetsData>) =>
  (options?.client ?? client).get<ListPetsResponse>({ url: '/v2/pets', ...options });

export const showPet = (options: Options<ShowPetData>) =>
  (options.client ?? client).get<ShowPetResponse>({ url: '/v2/pets/{petId}', ...options });

export const addPet = (options: Options<AddPetData>) =>
  (options.client ?? client).post<AddPetResponse>({
    url: '/v2/pets',
    ...options,
    headers: { 'Content-Type': 'application/json', ...options.headers },
  });

export const overridden = () => client.put({ url: '/v2/pets/archive', method: 'PATCH' });
"""
HELPER = """
let shopBase = '';

export function setShop(url: string) {
  shopBase = url;
}

function shopUrl(path: string): string {
  return `${shopBase}/shop${path}`;
}

export const cart = () => fetch(shopUrl('/cart'));
export const pay = (id: string) => fetch(shopUrl(`/carts/${id}/pay`), { method: 'POST' });
export const dynamic = (anything: string) => fetch(shopUrl(anything));
"""
ABSOLUTE = """
const WEATHER = 'https://api.weather.example.org';
const GEO_URL = 'https://geo.example.org/v1';

export async function forecast(input: string) {
  const city = input.trim().toLowerCase();
  return fetch(`${WEATHER}/${city}`);
}

export async function byParameter(place: string) {
  return fetch(`${WEATHER}/${place}`);
}

export async function byPath(endpoint: string) {
  const res = await fetch(`${GEO_URL}/${endpoint}`);
  return res;
}
"""


class GeneratedSdkTest(unittest.TestCase):
    def test_a_verb_given_an_options_object_sends_to_its_url(self):
        calls = Repository.calls(SDK, 'src/generated/sdk.gen.ts')
        self.assertTrue(
            {('GET', '/v2/pets'), ('GET', '/v2/pets/{petId}'), ('POST', '/v2/pets'), ('PATCH', '/v2/pets/archive')}
            <= set(calls)
        )

    def test_a_verb_of_a_whole_module_is_left_to_the_module(self):
        calls = Repository.calls("import * as rooms from './rooms';\nrooms.get({ url: '/r/1' });\n")
        self.assertEqual({}, calls)


class HelperArgumentsTest(unittest.TestCase):
    def test_a_url_helper_is_read_with_the_path_the_call_passes(self):
        calls = Repository.calls(HELPER, 'src/shop.ts')
        self.assertIn(('GET', '/shop/cart'), calls)
        self.assertIn(('POST', '/shop/carts/{id}/pay'), calls)
        self.assertNotIn(('GET', '/shop/{anything}'), calls)


class ValuesOnAPublicHostTest(unittest.TestCase):
    def test_a_path_of_values_the_function_holds_goes_to_the_host(self):
        calls = Repository.calls(ABSOLUTE, 'src/weather.ts')
        self.assertEqual('api.weather.example.org', calls['GET', '/{city}'].host)
        self.assertNotIn(('GET', '/{place}'), calls)  # the callers say what it holds
        self.assertNotIn(('GET', '/{endpoint}'), calls)  # a path, not a value


if __name__ == '__main__':
    unittest.main()
