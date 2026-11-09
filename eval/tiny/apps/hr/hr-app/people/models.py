from django.db import models


class Department(models.Model):
    name = models.CharField(max_length=100, unique=True)
    cost_center = models.CharField(max_length=20, blank=True)

    def __str__(self):
        return self.name


class Employee(models.Model):
    first_name = models.CharField(max_length=80)
    last_name = models.CharField(max_length=80)
    email = models.EmailField(unique=True)
    title = models.CharField(max_length=120)
    department = models.ForeignKey(Department, on_delete=models.PROTECT, related_name="employees")
    salary_band = models.CharField(max_length=4, default="B1")
    hired_on = models.DateField(auto_now_add=True)

    def __str__(self):
        return f"{self.first_name} {self.last_name}"


class LeaveRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending"
        APPROVED = "approved"
        REJECTED = "rejected"

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="leave_requests")
    start_date = models.DateField()
    end_date = models.DateField()
    reason = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
