from django.urls import path
from . import views

urlpatterns = [
    path('', views.meme_create, name='meme_create'),
    path('gallery/', views.meme_gallery, name='meme_gallery'),
] 