use tiny_http::{Header, Method, Request, Response, Server};

use crate::store::ScoreStore;

fn json_header() -> Header {
    Header::from_bytes(&b"Content-Type"[..], &b"application/json"[..]).expect("static header")
}

fn handle(request: Request, store: &ScoreStore) {
    let response = match (request.method(), request.url()) {
        (Method::Get, "/scores") => {
            println!("RECV H03 scorekeeper GET /scores");
            let body = serde_json::to_string(&store.snapshot()).unwrap_or_else(|_| "[]".into());
            Response::from_string(body).with_header(json_header())
        }
        (Method::Get, "/healthz") => Response::from_string("{\"ok\":true}").with_header(json_header()),
        _ => Response::from_string("not found").with_status_code(404),
    };
    if let Err(err) = request.respond(response) {
        eprintln!("failed to respond: {err}");
    }
}

pub fn serve_http(addr: &str, store: ScoreStore) {
    let server = Server::http(addr).expect("bind http listener");
    println!("scorekeeper http listening on {addr}");
    for request in server.incoming_requests() {
        handle(request, &store);
    }
}
