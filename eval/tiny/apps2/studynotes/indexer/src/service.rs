use std::sync::Mutex;

use tonic::{Request, Response, Status};

use crate::index::NoteIndex;
use crate::pb::indexer_server::Indexer;
use crate::pb::{
    IndexNoteReply, IndexNoteRequest, RemoveNoteReply, RemoveNoteRequest, SearchHit, SearchReply,
    SearchRequest,
};

#[derive(Default)]
pub struct IndexerService {
    index: Mutex<NoteIndex>,
}

#[tonic::async_trait]
impl Indexer for IndexerService {
    async fn index_note(
        &self,
        request: Request<IndexNoteRequest>,
    ) -> Result<Response<IndexNoteReply>, Status> {
        let req = request.into_inner();
        if req.note_id.is_empty() {
            return Err(Status::invalid_argument("note_id is required"));
        }
        let term_count = self
            .index
            .lock()
            .map_err(|_| Status::internal("index poisoned"))?
            .upsert(&req.note_id, &req.title, &req.body);
        println!("RECV T12 grpc IndexNote note_id={} terms={}", req.note_id, term_count);
        Ok(Response::new(IndexNoteReply {
            term_count: term_count as u32,
        }))
    }

    async fn search(
        &self,
        request: Request<SearchRequest>,
    ) -> Result<Response<SearchReply>, Status> {
        let req = request.into_inner();
        let limit = if req.limit == 0 { 10 } else { req.limit as usize };
        let hits = self
            .index
            .lock()
            .map_err(|_| Status::internal("index poisoned"))?
            .search(&req.query, limit);
        println!("RECV T13 grpc Search query={:?} hits={}", req.query, hits.len());
        Ok(Response::new(SearchReply {
            hits: hits
                .into_iter()
                .map(|(note_id, score)| SearchHit { note_id, score })
                .collect(),
        }))
    }

    async fn remove_note(
        &self,
        request: Request<RemoveNoteRequest>,
    ) -> Result<Response<RemoveNoteReply>, Status> {
        let req = request.into_inner();
        let removed = self
            .index
            .lock()
            .map_err(|_| Status::internal("index poisoned"))?
            .remove(&req.note_id);
        println!("RECV T14 grpc RemoveNote note_id={} removed={}", req.note_id, removed);
        Ok(Response::new(RemoveNoteReply { removed }))
    }
}
