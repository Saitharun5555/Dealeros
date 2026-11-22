from django.urls import path
from reconcile.views import disagreements

urlpatterns = [
    path("disagreements/", disagreements, name="disagreements"),
]
