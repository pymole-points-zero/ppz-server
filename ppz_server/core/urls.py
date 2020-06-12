from django.urls import path
from .views import (UploadTrainingGameView, NextGameView,
                    UploadNetworkView, DownloadNetworkView,
                    UploadMatchGameView)


urlpatterns = [
    path('next_game', NextGameView.as_view()),
    path('upload_network', UploadNetworkView.as_view()),
    path('download_network', DownloadNetworkView.as_view()),
    path('upload_match_game', UploadMatchGameView.as_view()),
    path('upload_training_game', UploadTrainingGameView.as_view()),
]

