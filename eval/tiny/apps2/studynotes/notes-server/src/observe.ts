// Runtime evidence for the eval harness: one RECV line per inbound link.
const procedureLinks: Record<string, string> = {
  'notes.create': 'T01',
  'notes.list': 'T02',
  'notes.byId': 'T03',
  'notes.delete': 'T04',
  'tags.list': 'T05',
  'tags.attach': 'T06',
  'notes.due': 'T09',
  'notes.markReminded': 'T10',
};

export function recv(linkId: string, detail: string): void {
  console.log(`RECV ${linkId} ${detail}`);
}

export function recvProcedure(path: string, type: string): void {
  const linkId = procedureLinks[path];
  if (linkId) recv(linkId, `trpc ${type} /trpc/${path}`);
}
