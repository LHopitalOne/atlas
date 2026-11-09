from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("departments", views.DepartmentViewSet)
router.register("employees", views.EmployeeViewSet)
router.register("leave-requests", views.LeaveRequestViewSet, basename="leave-request")

urlpatterns = [
    path("stats/headcount/", views.headcount, name="headcount"),
    path("health/", views.health, name="health"),
    path("", include(router.urls)),
]
