from django.urls import path

from learn.views import home

from . import views

urlpatterns = [
    path("", home, name="home"),
    path("hello/", views.hello, name="hello"),
    path("health/", views.health, name="health"),
]
