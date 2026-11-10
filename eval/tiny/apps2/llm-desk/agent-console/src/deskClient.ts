import type { NewTicket, Ticket, TicketFilter, TicketStatus } from './types.ts';

export class DeskApiError extends Error {
  constructor(
    readonly status: number,
    readonly path: string,
    message: string,
  ) {
    super(`desk ${path} -> ${status}: ${message}`);
  }
}

type Method = 'GET' | 'POST' | 'PATCH';

/** Typed client for the desk REST API. */
export class DeskClient {
  private readonly baseUrl: string;
  private readonly agent: string;

  constructor(baseUrl: string, agent: string) {
    this.baseUrl = baseUrl.replace(/\/+$/, '');
    this.agent = agent;
  }

  get agentName(): string {
    return this.agent;
  }

  private async send<T>(method: Method, path: string, body?: unknown): Promise<T> {
    const res = await fetch(this.baseUrl + path, {
      method,
      headers: {
        accept: 'application/json',
        'x-agent': this.agent,
        ...(body === undefined ? {} : { 'content-type': 'application/json' }),
      },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    if (!res.ok) {
      throw new DeskApiError(res.status, path, await res.text());
    }
    return (await res.json()) as T;
  }

  createTicket(ticket: NewTicket): Promise<Ticket> {
    return this.send<Ticket>('POST', '/api/tickets', ticket);
  }

  listTickets(filter: TicketFilter = {}): Promise<Ticket[]> {
    const query = new URLSearchParams();
    if (filter.team) query.set('team', filter.team);
    if (filter.urgent !== undefined) query.set('urgent', String(filter.urgent));
    const qs = query.size ? `?${query}` : '';
    return this.send<Ticket[]>('GET', `/api/tickets${qs}`);
  }

  getTicket(id: string): Promise<Ticket> {
    return this.send<Ticket>('GET', `/api/tickets/${encodeURIComponent(id)}`);
  }

  reply(id: string, opts: { body?: string; useDraft?: boolean }): Promise<Ticket> {
    return this.send<Ticket>('POST', `/api/tickets/${encodeURIComponent(id)}/reply`, {
      agent: this.agent,
      body: opts.body ?? null,
      use_draft: opts.useDraft ?? false,
    });
  }

  setStatus(id: string, status: TicketStatus): Promise<Ticket> {
    return this.send<Ticket>('PATCH', `/api/tickets/${encodeURIComponent(id)}`, { status });
  }

  eventsUrl(): URL {
    return new URL('/api/events/stream', this.baseUrl);
  }
}
