import { FormEvent, useEffect, useState } from "react";
import { hireEmployee, listDepartments, listEmployees } from "../api/hr";
import type { Department, Employee, NewEmployee } from "../api/types";

const EMPTY: NewEmployee = { first_name: "", last_name: "", email: "", title: "", department: 0, salary_band: "B1" };

export default function EmployeesPage() {
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [departments, setDepartments] = useState<Department[]>([]);
  const [draft, setDraft] = useState<NewEmployee>(EMPTY);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listEmployees().then(setEmployees);
    listDepartments().then((deps) => {
      setDepartments(deps);
      if (deps.length) setDraft((d) => ({ ...d, department: deps[0].id }));
    });
  }, []);

  async function onHire(e: FormEvent) {
    e.preventDefault();
    try {
      const hired = await hireEmployee(draft);
      setEmployees((list) => [...list, hired]);
      setDraft({ ...EMPTY, department: draft.department });
      setError(null);
    } catch (err) {
      setError(String(err));
    }
  }

  const field = (key: keyof NewEmployee) => ({
    value: String(draft[key]),
    onChange: (e: { target: { value: string } }) => setDraft({ ...draft, [key]: e.target.value }),
  });

  return (
    <section>
      <table>
        <tbody>
          {employees.map((e) => (
            <tr key={e.id}>
              <td>{e.first_name} {e.last_name}</td>
              <td>{e.title}</td>
              <td>{e.department_name}</td>
              <td>{e.salary_band}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <form onSubmit={onHire}>
        <h2>Hire</h2>
        <input placeholder="First name" {...field("first_name")} />
        <input placeholder="Last name" {...field("last_name")} />
        <input placeholder="Email" type="email" {...field("email")} />
        <input placeholder="Title" {...field("title")} />
        <select value={draft.department} onChange={(e) => setDraft({ ...draft, department: Number(e.target.value) })}>
          {departments.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
        </select>
        <select {...field("salary_band")}>
          {["B1", "B2", "B3", "B4"].map((b) => <option key={b}>{b}</option>)}
        </select>
        <button type="submit">Hire</button>
        {error && <p role="alert">{error}</p>}
      </form>
    </section>
  );
}
