import { FormEvent, useEffect, useState } from "react";
import { approveLeave, listLeaveRequests, requestLeave } from "../api/hr";
import type { LeaveRequest, NewLeaveRequest } from "../api/types";

export default function LeavePage() {
  const [requests, setRequests] = useState<LeaveRequest[]>([]);
  const [draft, setDraft] = useState<NewLeaveRequest>({ employee: 0, start_date: "", end_date: "", reason: "" });

  const reload = () => listLeaveRequests("pending").then(setRequests);
  useEffect(() => {
    reload();
  }, []);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    await requestLeave(draft);
    await reload();
  }

  async function onApprove(id: number) {
    await approveLeave(id);
    await reload();
  }

  return (
    <section>
      <ul>
        {requests.map((r) => (
          <li key={r.id}>
            #{r.employee} {r.start_date} to {r.end_date} ({r.reason})
            <button onClick={() => onApprove(r.id)}>Approve</button>
          </li>
        ))}
      </ul>
      <form onSubmit={onSubmit}>
        <input type="number" placeholder="Employee id" onChange={(e) => setDraft({ ...draft, employee: Number(e.target.value) })} />
        <input type="date" onChange={(e) => setDraft({ ...draft, start_date: e.target.value })} />
        <input type="date" onChange={(e) => setDraft({ ...draft, end_date: e.target.value })} />
        <input placeholder="Reason" onChange={(e) => setDraft({ ...draft, reason: e.target.value })} />
        <button type="submit">Request leave</button>
      </form>
    </section>
  );
}
