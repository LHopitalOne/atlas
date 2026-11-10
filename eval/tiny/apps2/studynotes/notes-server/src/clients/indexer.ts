import path from 'node:path';
import { fileURLToPath } from 'node:url';
import * as grpc from '@grpc/grpc-js';
import * as protoLoader from '@grpc/proto-loader';
import { config } from '../config';

const PROTO_PATH = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../proto/indexer.proto');

const packageDefinition = protoLoader.loadSync(PROTO_PATH, {
  keepCase: false,
  longs: Number,
  defaults: true,
});
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const proto = grpc.loadPackageDefinition(packageDefinition) as any;

const client = new proto.studynotes.indexer.v1.Indexer(
  config.indexerAddr,
  grpc.credentials.createInsecure(),
);

function unary<Req, Res>(method: string, request: Req): Promise<Res> {
  return new Promise((resolve, reject) => {
    client[method](request, { deadline: Date.now() + 3000 }, (err: grpc.ServiceError | null, res: Res) =>
      err ? reject(err) : resolve(res),
    );
  });
}

export interface SearchHit {
  noteId: string;
  score: number;
}

export const indexer = {
  indexNote(noteId: string, title: string, body: string) {
    return unary<object, { termCount: number }>('indexNote', { noteId, title, body });
  },
  async search(query: string, limit = 10): Promise<SearchHit[]> {
    const reply = await unary<object, { hits: SearchHit[] }>('search', { query, limit });
    return reply.hits;
  },
  removeNote(noteId: string) {
    return client.removeNote({ noteId }, (err: grpc.ServiceError | null) => {
      if (err) console.error(`indexer.removeNote failed: ${err.message}`);
    });
  },
};
