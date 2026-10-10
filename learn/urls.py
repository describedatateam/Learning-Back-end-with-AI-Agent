from django.urls import path

from . import views

app_name = 'learn'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('paths/', views.path_catalog, name='catalog'),
    path('paths/generate/', views.generate_path, name='generate'),
    path('languages/', views.supported_languages, name='languages'),
    path('paths/<slug:slug>/', views.path_detail, name='path'),
    path('paths/<slug:slug>/placement/', views.placement_test, name='placement'),
    path('paths/<slug:slug>/delete/', views.delete_path, name='delete_path'),
    path('paths/<slug:slug>/chapters/<slug:chapter>/', views.chapter_detail, name='chapter'),
    path('paths/<slug:slug>/choose/', views.choose_path, name='choose_path'),
    path('paths/<slug:slug>/skip/', views.skip_path, name='skip_path'),
    path('flashcards/', views.flashcards_page, name='flashcards'),
    path('flashcards/review/', views.flashcards_review, name='flashcards_review'),
    path('flashcards/run/', views.flashcards_run, name='flashcards_run'),
    path('flashcards/add/<slug:chapter>/', views.flashcards_add, name='flashcards_add'),
    path('flashcards/remove/<slug:chapter>/', views.flashcards_remove, name='flashcards_remove'),
    path('project/', views.project_home, name='project'),
    path('project/<int:project_id>/', views.project_detail, name='project_detail'),
    path('project/<int:project_id>/check/', views.project_check, name='project_check'),
    path('project/<int:project_id>/update/', views.project_update, name='project_update'),
    path('project/<int:project_id>/delete/', views.project_delete, name='project_delete'),
    path('portfolio/', views.coming_soon, {'section': 'portfolio'}, name='portfolio'),
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
