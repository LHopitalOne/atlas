import { useState } from "react";
import EmployeesPage from "./components/EmployeesPage";
import LeavePage from "./components/LeavePage";
import HeadcountBadge from "./components/HeadcountBadge";

type Tab = "employees" | "leave";

export default function App() {
  const [tab, setTab] = useState<Tab>("employees");
  return (
    <main>
      <header>
        <h1>People</h1>
        <HeadcountBadge />
        <nav>
          <button onClick={() => setTab("employees")} disabled={tab === "employees"}>Employees</button>
          <button onClick={() => setTab("leave")} disabled={tab === "leave"}>Leave</button>
        </nav>
      </header>
      {tab === "employees" ? <EmployeesPage /> : <LeavePage />}
    </main>
  );
}
