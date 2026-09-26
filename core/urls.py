from django.urls import path
from django.views.generic import RedirectView

from . import views

urlpatterns = [
    path("", RedirectView.as_view(url="/learn/"), name="home"),
    path("hello/", views.hello, name="hello"),
    path("health/", views.health, name="health"),
]
