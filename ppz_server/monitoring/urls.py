from django.urls import path
from .views import (Progress, MatchesView, NetworksView,)


urlpatterns = [
    path('progress/<int:training_run_id>', Progress.as_view()),
    path('matches', MatchesView.as_view()),
    path('networks', NetworksView.as_view()),
]
