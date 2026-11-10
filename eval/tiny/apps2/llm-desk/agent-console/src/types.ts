export type TicketStatus = 'new' | 'triaged' | 'answered' | 'closed';

export interface NewTicket {
  customer: string;
  subject: string;
  body: string;
}

export interface Ticket extends NewTicket {
  id: string;
  status: TicketStatus;
  urgent: boolean | null;
  urgency: number | null;
  team: string | null;
  replies: string[];
  created_at: string;
}

export interface TicketFilter {
  team?: string;
  urgent?: boolean;
}

export interface DeskEvent<T = unknown> {
  id?: string;
  event: string;
  data: T;
}
