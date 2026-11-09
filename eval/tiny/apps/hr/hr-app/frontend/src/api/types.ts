export interface Department {
  id: number;
  name: string;
  cost_center: string;
}

export interface Employee {
  id: number;
  first_name: string;
  last_name: string;
  email: string;
  title: string;
  department: number;
  department_name: string;
  salary_band: string;
  hired_on: string;
}

export type NewEmployee = Omit<Employee, "id" | "department_name" | "hired_on">;

export type LeaveStatus = "pending" | "approved" | "rejected";

export interface LeaveRequest {
  id: number;
  employee: number;
  start_date: string;
  end_date: string;
  reason: string;
  status: LeaveStatus;
}

export type NewLeaveRequest = Pick<LeaveRequest, "employee" | "start_date" | "end_date" | "reason">;

export interface Headcount {
  total: number;
  by_department: { department: string; count: number }[];
}
