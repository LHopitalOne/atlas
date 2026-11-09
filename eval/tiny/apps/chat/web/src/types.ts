export interface Room {
  id: string;
  name: string;
  createdAt: string;
}

export interface Message {
  id: string;
  roomId: string;
  author: string;
  text: string;
  sentAt: string;
}

export interface ReportTicket {
  ticketId: string;
  openReports: number;
}

export type ServerFrame =
  | { type: 'message'; message: Message }
  | { type: 'rejected'; clientId?: string; reason: string }
  | { type: 'error'; error: string };
