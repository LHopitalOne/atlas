export interface TriagedEntry {
  ticketId: string;
  team: string;
  urgent: boolean;
  createdAt: string;
}

export interface DailyCount {
  day: string;
  team: string;
  total: number;
  urgent: number;
}

/** Rolling per-day, per-team counters. */
export class DailyCounts {
  private readonly rows = new Map<string, DailyCount>();
  private dirty = false;

  add(entry: TriagedEntry): void {
    const day = entry.createdAt.slice(0, 10);
    const key = `${day}|${entry.team}`;
    const row = this.rows.get(key) ?? { day, team: entry.team, total: 0, urgent: 0 };
    row.total += 1;
    if (entry.urgent) row.urgent += 1;
    this.rows.set(key, row);
    this.dirty = true;
  }

  get hasChanges(): boolean {
    return this.dirty;
  }

  snapshot(): DailyCount[] {
    this.dirty = false;
    return [...this.rows.values()].sort((a, b) => a.day.localeCompare(b.day) || a.team.localeCompare(b.team));
  }
}

export function parseFields(fields: string[]): TriagedEntry {
  const map: Record<string, string> = {};
  for (let i = 0; i < fields.length; i += 2) map[fields[i]] = fields[i + 1];
  return {
    ticketId: map.ticket_id,
    team: map.team ?? 'unassigned',
    urgent: map.urgent === '1',
    createdAt: map.created_at ?? new Date().toISOString(),
  };
}
