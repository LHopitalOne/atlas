from django.db import transaction
from django.db.models import Count
from rest_framework import status, viewsets
from rest_framework.decorators import action, api_view
from rest_framework.response import Response

from . import events
from .compensation import band_range
from .models import Department, Employee, LeaveRequest
from .serializers import DepartmentSerializer, EmployeeSerializer, LeaveRequestSerializer


class DepartmentViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Department.objects.order_by("name")
    serializer_class = DepartmentSerializer


class EmployeeViewSet(viewsets.ModelViewSet):
    queryset = Employee.objects.select_related("department").order_by("last_name")
    serializer_class = EmployeeSerializer

    def perform_create(self, serializer):
        employee = serializer.save()
        transaction.on_commit(lambda: events.employee_hired(employee))

    @action(detail=True, methods=["get"], url_path="salary-band")
    def salary_band(self, request, pk=None):
        employee = self.get_object()
        return Response({"employee_id": employee.id, **band_range(employee.salary_band)})


class LeaveRequestViewSet(viewsets.ModelViewSet):
    serializer_class = LeaveRequestSerializer

    def get_queryset(self):
        qs = LeaveRequest.objects.select_related("employee").order_by("-created_at")
        wanted = self.request.query_params.get("status")
        return qs.filter(status=wanted) if wanted else qs

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        leave = self.get_object()
        if leave.status != LeaveRequest.Status.PENDING:
            return Response({"detail": "Already decided"}, status=status.HTTP_409_CONFLICT)
        leave.status = LeaveRequest.Status.APPROVED
        leave.save(update_fields=["status"])
        return Response(self.get_serializer(leave).data)


@api_view(["GET"])
def headcount(request):
    rows = Department.objects.annotate(total=Count("employees")).order_by("name")
    return Response({
        "total": Employee.objects.count(),
        "by_department": [{"department": d.name, "count": d.total} for d in rows],
    })


@api_view(["GET"])
def health(request):
    return Response({"status": "ok"})
