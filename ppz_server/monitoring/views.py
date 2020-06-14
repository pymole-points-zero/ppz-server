from rest_framework.views import APIView
from rest_framework.response import Response
from core.models import Network, Match, TrainingRun, TrainingGame
from django.db.models import F
from datetime import datetime, timedelta


class Progress(APIView):
    def get(self, request, training_run_id):
        chart = self.chart(training_run_id)
        last_day_games_count = TrainingGame.objects.filter(
            created_at__gte=datetime.today()-timedelta(days=1)).count()
        last_hour_games_count = TrainingGame.objects.filter(
            created_at__gte=datetime.today() - timedelta(hours=1)).count()

        response = {
            'last_day_games_count': last_day_games_count,
            'last_hour_games_count': last_hour_games_count,
            'chart': chart
        }

        return Response(response)

    def chart(self, training_run_id):
        networks = Network.objects.filter(training_run_id=training_run_id).values(
            'network_number', 'elo', 'games_played').order_by('id').all()

        remove_idx = []
        aggregated_count = 0
        for idx, network in enumerate(networks):
            if network['elo'] is None:
                remove_idx.append(idx)
                continue

            if network['games_played'] == 0:
                aggregated_count += 1
            else:
                aggregated_count += network['games_played']

            network['games_played'] = aggregated_count

        # remove rating networks with undefined rating
        networks = list(networks)
        remove_idx.reverse()
        for idx in remove_idx:
            networks.pop(idx)

        # limit response
        networks = networks[:100]

        return networks



class NetworksView(APIView):
    def get(self, request):
        networks = Network.objects.values('network_number', 'sha', 'training_run_id', 'blocks',
                                          'filters', 'create_at', 'elo', 'games_played'
                                          ).order_by('-id')[:100]

        return Response(networks)


class MatchesView(APIView):
    def get(self, request):
        matches = Match.objects.values('id', 'training_run_id', 'passed',
                                        'done', 'create_at').order_by('-id')[:100]

        return Response(matches)


class TrainingRunsView(APIView):
    def get(self, request):
        training_runs = TrainingRun.objects.annotate(
            best_network__network_number=F('best_network_number')).values(
            'best_network__network_number', 'active',
            'description', 'training_params').all()

        return Response(training_runs)

