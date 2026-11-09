import {
  approveLeave, getHeadcount, hireEmployee, listDepartments, listEmployees, listLeaveRequests, requestLeave,
} from "../hr-app/frontend/src/api/hr";

const origin = process.env.HR_WEB_ORIGIN ?? "http://127.0.0.1:41101";
const browserFetch = globalThis.fetch;
globalThis.fetch = (input: RequestInfo | URL, init?: RequestInit) =>
  browserFetch(typeof input === "string" && input.startsWith("/") ? new URL(input, origin) : input, init);

async function main() {
  const departments = await listDepartments();
  console.log(`departments: ${departments.map((d) => d.name).join(", ")}`);

  const hired = await hireEmployee({
    first_name: "Ada",
    last_name: "Lovelace",
    email: `ada.${Date.now()}@example.com`,
    title: "Engineer",
    department: departments[0].id,
    salary_band: "B3",
  });
  console.log(`hired employee #${hired.id}`);

  console.log(`employees: ${(await listEmployees()).length}`);

  const leave = await requestLeave({
    employee: hired.id, start_date: "2026-12-21", end_date: "2026-12-31", reason: "Holidays",
  });
  console.log(`pending leave requests: ${(await listLeaveRequests("pending")).length}`);
  console.log(`leave #${leave.id} is now ${(await approveLeave(leave.id)).status}`);

  console.log(`headcount: ${(await getHeadcount()).total}`);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
