from django.urls import path

from leave import views

urlpatterns = [
    path("api/v1/leave", views.leave_feed, name="api-leave"),
    path("time-off/", views.time_off, name="time-off"),
    path("time-off/add/", views.add, name="time-off-add"),
    path("time-off/request/", views.request_time_off, name="time-off-request"),
    path("time-off/mine/", views.mine, name="time-off-mine"),
    path("time-off/approve/", views.waiting, name="time-off-approve"),
    path("time-off/planner/", views.planner, name="time-off-planner"),
    path("time-off/bank-holidays/", views.bank_holidays_index, name="bank-holidays"),
    path("time-off/bank-holidays/<str:day>/everyone/", views.bank_holiday_everyone, name="bank-holiday-everyone"),
    path("time-off/blackouts/", views.blackouts_index, name="blackouts"),
    path("time-off/blackouts/add/", views.blackout_add, name="blackout-add"),
    path("time-off/blackouts/<int:pk>/edit/", views.blackout_edit, name="blackout-edit"),
    path("time-off/blackouts/<int:pk>/delete/", views.blackout_delete, name="blackout-delete"),
    path("time-off/year-end/", views.year_end, name="time-off-year-end"),
    path("time-off/year-end/<int:pk>/decide/", views.year_end_decide, name="time-off-year-end-decide"),
    path("time-off/<int:pk>/", views.view, name="time-off-view"),
    path("time-off/<int:pk>/edit/", views.edit, name="time-off-edit"),
    path("time-off/<int:pk>/cancel/", views.cancel, name="time-off-cancel"),
    path("time-off/<int:pk>/decide/", views.decide, name="time-off-decide"),
    path("reports/leave/", views.leave_report, name="report-leave"),
    path("settings/leave-types/", views.types_index, name="leave-types"),
    path("settings/leave-types/add/", views.type_add, name="leave-type-add"),
    path("settings/leave-types/<int:pk>/edit/", views.type_edit, name="leave-type-edit"),
    path("settings/leave/", views.leave_settings, name="leave-settings"),
    path("staff/<int:pk>/leave/adjust/", views.adjust, name="leave-adjust"),
    path("staff/<int:pk>/leave/hours-change/", views.hours_change, name="leave-hours-change"),
]
