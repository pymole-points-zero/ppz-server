from django.urls import path
from .views import (UploadGameView, NextGameView,
                    UploadNetworkView, DownloadNetworkView,
                    MatchGameResultView)



urlpatterns = [
    path('upload_game', UploadGameView.as_view()),
    path('next_game', NextGameView.as_view()),
    path('upload_network', UploadNetworkView.as_view()),
    path('download_network', DownloadNetworkView.as_view()),
    path('match_game_result', MatchGameResultView.as_view()),
]