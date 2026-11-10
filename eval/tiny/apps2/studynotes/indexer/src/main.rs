mod index;
mod service;

pub mod pb {
    tonic::include_proto!("studynotes.indexer.v1");
}

use std::net::SocketAddr;

use pb::indexer_server::IndexerServer;
use service::IndexerService;
use tonic::transport::Server;

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let addr: SocketAddr = std::env::var("INDEXER_LISTEN")
        .unwrap_or_else(|_| "127.0.0.1:45020".to_string())
        .parse()?;
    println!("indexer listening on {addr}");

    Server::builder()
        .add_service(IndexerServer::new(IndexerService::default()))
        .serve_with_shutdown(addr, async {
            let _ = tokio::signal::ctrl_c().await;
        })
        .await?;
    Ok(())
}
