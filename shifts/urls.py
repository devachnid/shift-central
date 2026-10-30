from django.urls import path

from shifts.views import api, dialogs, grid

urlpatterns = [
    path("rota/api/window/", api.window_view, name="api-window"),
    path("rota/api/cell/", api.cell, name="api-cell"),
    path("rota/api/cell/items/", api.cell_items, name="api-cell-items"),
    path("rota/api/entries/<int:pk>/", api.entry_patch, name="api-entry"),
    path("rota/api/move/", api.move, name="api-move"),
    path("rota/api/paste/", api.paste, name="api-paste"),
    path("rota/api/clear/", api.clear, name="api-clear"),
    path("rota/api/replace/", api.replace, name="api-replace"),
    path("rota/api/order/", api.order, name="api-order"),
    path("rota/", grid.grid, name="rota"),
    path("rota/download/", grid.download, name="rota-download"),
    path("rota/shift/<int:person_pk>/<str:day>/", dialogs.shift, name="rota-shift"),
    path("rota/shift/<int:person_pk>/<str:day>/<int:entry_pk>/", dialogs.shift, name="rota-shift-edit"),
    path("rota/options/", dialogs.options_view, name="rota-options"),
    path("rota/filters/", dialogs.filters, name="rota-filters"),
    path("rota/replace/", dialogs.replace, name="rota-replace"),
    path("rota/notify/", dialogs.notify_view, name="rota-notify"),
    path("rota/templates/", dialogs.templates_list, name="rota-templates"),
    path("rota/templates/save/", dialogs.template_save, name="rota-template-save"),
    path("rota/templates/<int:pk>/apply/", dialogs.template_apply, name="rota-template-apply"),
    path("rota/templates/<int:pk>/rename/", dialogs.template_rename, name="rota-template-rename"),
    path("rota/templates/<int:pk>/delete/", dialogs.template_delete, name="rota-template-delete"),
]
