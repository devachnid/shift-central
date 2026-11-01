from django.urls import path

from uploads import views

urlpatterns = [
    path("uploads/", views.shared, name="uploads"),
    path("uploads/<int:pk>/download/", views.download, name="upload-download"),
    path("uploads/<int:pk>/delete/", views.delete, name="upload-delete"),
    path("staff/<int:pk>/uploads/", views.person, name="person-uploads"),
]
