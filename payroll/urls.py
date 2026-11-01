from django.urls import path

from payroll import views

urlpatterns = [
    path("reports/payroll/", views.payroll, name="report-payroll"),
    path("reports/payroll/sent/", views.mark_sent, name="payroll-sent"),
]
