import unittest

from .support import RustRepo

ACTIX = """
use actix_web::{web, App, HttpServer, get, post};

#[get("/hello/{name}")]
async fn hello(name: web::Path<String>) -> String { name.into_inner() }

#[post("/items")]
async fn create() -> HttpResponse { HttpResponse::Ok().finish() }

#[actix_web::route("/multi", method = "GET", method = "HEAD")]
async fn multi() -> HttpResponse { HttpResponse::Ok().finish() }

fn config(cfg: &mut web::ServiceConfig) {
    cfg.service(web::resource("/configured").route(web::put().to(put_handler)));
}

#[actix_web::main]
async fn main() -> std::io::Result<()> {
    HttpServer::new(|| {
        App::new()
            .service(hello)
            .service(
                web::scope("/api")
                    .service(create)
                    .service(web::resource("/users/{id:\\\\d+}").route(web::post().to(add_user)).get(get_user))
                    .route("/ping", web::get().to(ping))
                    .service(web::resource("/any").to(anything)),
            )
            .configure(config)
    })
    .bind(("127.0.0.1", 8080))?
    .run()
    .await
}

#[cfg(test)]
mod tests {
    #[get("/test-only")]
    async fn fake() -> String { String::new() }
}
"""


class ActixTest(unittest.TestCase):
    def test_actix_routes(self):
        found = RustRepo({'src/main.rs': ACTIX}).routes()
        self.assertEqual(
            sorted(found),
            [
                ('ANY', '/api/any'),
                ('GET', '/api/ping'),
                ('GET', '/api/users/{id}'),
                ('GET', '/hello/{name}'),
                ('GET', '/multi'),
                ('HEAD', '/multi'),
                ('POST', '/api/items'),
                ('POST', '/api/users/{id}'),
                ('PUT', '/configured'),
            ],
        )
        hello = found[('GET', '/hello/{name}')]
        self.assertEqual((hello.handler, hello.framework, hello.line), ('hello', 'actix', 4))
        self.assertEqual(found[('POST', '/api/users/{id}')].handler, 'add_user')
        self.assertEqual(found[('GET', '/api/ping')].handler, 'ping')
        self.assertEqual(found[('GET', '/api/ping')].framework, 'actix')

    def test_unmounted_attribute_route(self):
        source = 'use actix_web::get;\n#[get("/alone")]\n// doc\nasync fn alone() {}\n#[get("rel")]\nfn r() {}\n'
        found = RustRepo({'src/h.rs': source}).routes()
        self.assertEqual(sorted(found), [('GET', '/alone')])

    def test_raw_string_attribute_route(self):
        source = 'use actix_web::get;\n#[get(r"/raw")]\nasync fn e() {}\n#[get(r#"/hash"#)]\nasync fn h() {}\n'
        found = RustRepo({'src/h.rs': source}).routes()
        self.assertEqual(sorted(found), [('GET', '/hash'), ('GET', '/raw')])
        self.assertEqual(found[('GET', '/raw')].framework, 'actix')

    def test_route_attribute_without_methods_and_attributes_on_other_items(self):
        source = (
            'use actix_web::route;\n'
            '#[route("/all")]\nasync fn all() {}\n'
            '#[get("/on-struct")]\nstruct S;\n'
            '#[get]\nfn bare() {}\n'
            '#[inline]\nfn plain() {}\n'
        )
        found = RustRepo({'src/h.rs': source}).routes()
        self.assertEqual(sorted(found), [('ANY', '/all')])

    def test_tail_captures(self):
        source = 'use actix_web::get;\n#[get("/files/{tail}*")]\nasync fn files() {}\n'
        self.assertIn(('GET', '/files/{*tail}'), RustRepo({'src/h.rs': source}).routes())


if __name__ == '__main__':
    unittest.main()
