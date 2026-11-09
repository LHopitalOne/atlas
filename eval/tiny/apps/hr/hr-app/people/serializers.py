from rest_framework import serializers

from .compensation import SALARY_BANDS
from .models import Department, Employee, LeaveRequest


class DepartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = ["id", "name", "cost_center"]


class EmployeeSerializer(serializers.ModelSerializer):
    department_name = serializers.CharField(source="department.name", read_only=True)

    class Meta:
        model = Employee
        fields = [
            "id", "first_name", "last_name", "email", "title",
            "department", "department_name", "salary_band", "hired_on",
        ]
        read_only_fields = ["hired_on"]

    def validate_salary_band(self, value):
        if value not in SALARY_BANDS:
            raise serializers.ValidationError(f"Unknown salary band {value}")
        return value


class LeaveRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = LeaveRequest
        fields = ["id", "employee", "start_date", "end_date", "reason", "status", "created_at"]
        read_only_fields = ["status", "created_at"]

    def validate(self, attrs):
        if attrs["end_date"] < attrs["start_date"]:
            raise serializers.ValidationError("end_date must not be before start_date")
        return attrs
