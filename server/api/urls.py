from django.urls import path

from . import views

urlpatterns = [
    path("api/health", views.health, name="health"),
    path("api/debate/<str:ticker>", views.debate, name="debate"),
]
