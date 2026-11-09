import { apiFetch } from "./client";
import type {
  Department, Employee, Headcount, LeaveRequest, LeaveStatus, NewEmployee, NewLeaveRequest,
} from "./types";

export const listDepartments = () => apiFetch<Department[]>("/api/departments/");

export const listEmployees = () => apiFetch<Employee[]>("/api/employees/");

export const hireEmployee = (employee: NewEmployee) =>
  apiFetch<Employee>("/api/employees/", { method: "POST", body: employee });

export const listLeaveRequests = (status?: LeaveStatus) =>
  apiFetch<LeaveRequest[]>(`/api/leave-requests/${status ? `?status=${status}` : ""}`);

export const requestLeave = (request: NewLeaveRequest) =>
  apiFetch<LeaveRequest>("/api/leave-requests/", { method: "POST", body: request });

export const approveLeave = (id: number) =>
  apiFetch<LeaveRequest>(`/api/leave-requests/${id}/approve/`, { method: "POST" });

export const getHeadcount = () => apiFetch<Headcount>("/api/stats/headcount/");
