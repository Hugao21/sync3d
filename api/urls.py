from django.urls import path

from . import views

urlpatterns = [
    path('impressoras/', views.ImpressoraList.as_view()),
    path('impressoras/<int:pk>/', views.ImpressoraDetail.as_view()),
    path('filamentos/', views.FilamentoList.as_view()),
    path('filamentos/<int:pk>/', views.FilamentoDetail.as_view()),
    path('agendamentos/', views.AgendamentoList.as_view()),
    path('agendamentos/<int:pk>/', views.AgendamentoDetail.as_view()),
]
