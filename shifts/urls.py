from django.urls import path

from shifts.views import api

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
]
