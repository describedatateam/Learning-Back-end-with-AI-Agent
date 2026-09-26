from django.urls import path

from . import views

app_name = 'learn'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('tutor/', views.tutor_page, name='tutor'),
    path('notebook/', views.notebook_page, name='notebook'),
    path('notebook/<slug:slug>/generate/', views.notebook_generate, name='notebook_generate'),
    path('tutor/<slug:topic>/ask/', views.tutor_ask, name='tutor_ask'),
    path('tutor/<slug:topic>/clear/', views.tutor_clear, name='tutor_clear'),
    path('<slug:slug>/', views.exercise_detail, name='exercise'),
    path('<slug:slug>/run/', views.run, name='run'),
    path('<slug:slug>/run-selection/', views.run_code_selection, name='run_selection'),
    path('<slug:slug>/quiz/', views.quiz, name='quiz'),
    path('<slug:slug>/solution/', views.solution, name='solution'),
    path('<slug:slug>/slides/', views.slides, name='slides'),
]
