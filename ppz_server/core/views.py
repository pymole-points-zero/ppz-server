from rest_framework.views import APIView
from rest_framework.response import Response
from .models import TrainingGame, User, Match, MatchGame, TrainingRun, Network
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import MultiPartParser, JSONParser
import gzip
import hashlib
from django.conf import settings
from django.http import FileResponse
from django.core.exceptions import ObjectDoesNotExist

# TODO https://docs.djangoproject.com/en/3.0/topics/db/optimization/


def check_user(request):
    username = request.data.get('username', None)
    if not username:
        raise ValidationError({'error': 'User must have a username field.'})

    user = User.objects.filter(username=username).first()
    if user:
        return user

    password = request.data.get('password', None)
    if not password:
        raise ValidationError({'error': 'User must have a password field.'})

    user = User.objects.create_user(username, password, commit=True)
    return user


# TODO использовать сериализаторы для проверки присланной информации

class NextGameView(APIView):
    def post(self, request, *args, **kwargs):
        user = check_user(request)

        training_run = TrainingRun.objects.select_related('best_network').filter(active=True).order_by('?').first()

        if training_run is None:
            return Response({'error': 'No training runs.'})

        # узнал, что невозможно сохранить
        user.assigned_training_run = training_run
        user.save(update_fields=['assigned_training_run'])

        match = Match.objects.filter(training_run=training_run, done=False).first()

        if match:
            match_game = MatchGame.objects.create(user=user, match=match)
            candidate_turns_first = bool(match_game.id % 2)

            match_game.candidate_turns_first = candidate_turns_first
            match_game.save()

            result = {
                'game_type': 'match',
                'match_game_id': match_game.id,
                'best_network_sha': match.current_best.sha,
                'candidate_sha': match.candidate.sha,
                'parameters': match.parameters,
                'candidate_turns_first': candidate_turns_first
            }

            return Response(result)

        result = {
            "game_type": "train",
            "training_run_id": training_run.id,
            "network_id": training_run.best_network.id,
            "best_network_sha": training_run.best_network.sha,
            "parameters": training_run.training_parameters,
            "keep_time": 16,
        }

        return Response(result)


class UploadNetworkView(APIView):
    parser_classes = [MultiPartParser]

    def post(self, request):
        new_network_file = request.FILES.get('network', None)
        if new_network_file is None:
            raise ValidationError({'error': 'Need network file.'})

        prev_network_sha = request.data.get('prev_delta_sha', None)
        if prev_network_sha is not None:
            prev_network = Network.objects.filter(sha=prev_network_sha).first()

            if prev_network is None:
                raise ValidationError({'error': 'Unknown previous network'})

            try:
                prevData = gzip.open(prev_network.file.name).read()
            except OSError:
                raise ValidationError({'error': 'Corrupted previous network.'})

            deltaData = gzip.decompress(new_network_file.read())
            if len(prevData) != len(deltaData):
                return ValidationError({'error': "Data lengths don't match."})

            changes = bytes(p ^ d for d, p in zip(deltaData, prevData))

            sha = hashlib.sha256(changes).hexdigest()
        else:
            sha = hashlib.sha256(gzip.decompress(new_network_file.read())).hexdigest()

        if Network.objects.filter(sha=sha).exists():
            raise ValidationError({'error': "Network exists."})

        training_run_id = int(request.data.get('training_run_id', 0))

        training_run = TrainingRun.objects.select_related('best_network').filter(id=training_run_id).first()
        if training_run is None:
            raise ValidationError({'error': "Training run does not exists."})

        training_run.last_network += 1
        training_run.save(update_fields=['last_network'])

        filters = request.data.get('filters', 0)
        layers = request.data.get('layers', 0)

        new_network = Network.objects.create(
            training_run=training_run, layers=layers, filters=filters, sha=sha,
            network_number=training_run.last_network
        )

        new_network.file.save(sha, new_network_file, save=True)

        # create match
        best_network = training_run.best_network
        if best_network is None:
            raise ValidationError({'message': "Uploaded, but no best network."})

        Match.objects.create(training_run=training_run, candidate=new_network, current_best=best_network,
                             parameters=settings.MATCHES.get('parameters'),
                             games_to_finish=settings.MATCHES['games_to_finish'])

        # regression check
        # prev_network1 = training_run.networks.filter(network_number=best_network.network_number - 3).first()
        # if prev_network1 is not None:
        #     Match.objects.create(training_run=training_run, candidate=prev_network1, current_best=best_network,
        #                      params=settings.MATCHES.get('params'))
        #
        # prev_network2 = training_run.networks.filter(network_number=best_network.network_number - 10).first()
        # if prev_network2 is not None:
        #     Match.objects.create(training_run=training_run, candidate=prev_network2, current_best=best_network,
        #                      params=settings.MATCHES.get('params'))

        return Response({'message': 'Network uploaded successfully.'})


class UploadTrainingGameView(APIView):
    parser_classes = [MultiPartParser]

    def post(self, request):
        user = check_user(request)

        training_run_id = request.data.get('training_run_id', None)
        if training_run_id is None:
            raise ValidationError({'error': 'Need training run id.'})

        try:
            training_run_id = int(training_run_id)
        except ValueError:
            raise ValidationError({'error': 'Training run id need to be an integer.'})

        try:
            training_run = TrainingRun.objects.get(id=training_run_id)
        except ObjectDoesNotExist:
            raise ValidationError({'error': 'Invalid training id.'})

        network_id = request.data.get('network_id', None)
        if network_id is None:
            raise ValidationError({'error': 'Provide network id.'})

        try:
            network_id = int(network_id)
        except ValueError:
            raise ValidationError({'error': 'Network id need to be an integer.'})

        try:
            network = Network.objects.get(id=network_id)
        except ObjectDoesNotExist:
            raise ValidationError({'error': 'Invalid network id.'})

        training_game_sgf = request.data.get('training_game_sgf', None)
        if training_game_sgf is None:
            raise ValidationError({'error': 'Need a training game sgf.'})

        if len(training_game_sgf) == 0:
            raise ValidationError({'error': 'Training game is empty.'})

        network.games_played += 1
        network.save(update_fields=['games_played'])

        training_run.last_game += 1
        training_run.save(update_fields=['last_game'])

        training_game = TrainingGame.objects.create(user=user, training_run=training_run,
                                                    network=network, game_number=training_run.last_game,
                                                    sgf=training_game_sgf)

        return Response({'message': 'Training game uploaded successfully.'})


class DownloadNetworkView(APIView):
    def get(self, request):
        sha = request.data.get('sha', None)
        if sha is None:
            raise ValidationError({'error': 'No sha.'})

        network = Network.objects.filter(sha=sha).first()
        if network is None:
            raise ValidationError({'error': 'Invalid sha.'})

        network.file.open()
        return FileResponse(network.file, filename=network.file.name)


class UploadMatchGameView(APIView):
    parser_classes = [MultiPartParser]

    def post(self, request):
        user = check_user(request)

        match_game_sgf = request.data.get('match_game_sgf', None)
        if match_game_sgf is None:
            raise ValidationError({'error': 'No match game sgf.'})

        if len(match_game_sgf) == 0:
            raise ValidationError({'error': 'Empty match game sgf.'})

        match_game_id = request.data.get('match_game_id', None)

        if match_game_id is None:
            raise ValidationError({'error': 'No match game id.'})

        try:
            match_game_id = int(match_game_id)
        except ValueError:
            raise ValidationError({'error': 'Match game id need to be an integer.'})

        match_game = MatchGame.objects.select_related('match').filter(id=match_game_id).first()
        if match_game is None:
            raise ValidationError({'error': 'Invalid match game.'})

        result = request.data.get('result', None)

        if result is None:
            raise ValidationError({'error': 'No result.'})

        try:
            result = int(result)
        except ValueError:
            raise ValidationError({'error': 'Result need to be an integer.'})

        match = match_game.match
        if result == 0:
            match.draws += 1
            update_fields = ['draws']
        elif result == -1:
            match.best_wins += 1
            update_fields = ['best_wins']
        elif result == 1:
            match.candidate_wins += 1
            update_fields = ['candidate_wins']
        else:
            raise ValidationError({'error': 'Bad result.'})

        match_game.result = result
        match_game.done = True
        match_game.sgf = match_game_sgf

        match_game.save(update_fields=['result', 'done'])

        if match.done:
            raise ValidationError({'error': 'Match already is done.'})

        games_count = match.candidate_wins + match.best_wins + match.draws

        if games_count >= match.games_to_finish:
            match.done = True

            w = match.candidate_wins/games_count
            d = match.draws/games_count

            mu = w + d/2

            passed = mu >= settings.MATCHES['update_threshold']

            match.passed = passed

            if passed:
                match.training_run.best_network = match.candidate
                match.training_run.save(update_fields='best_network')

            update_fields += ['done', 'passed']

        match.save(update_fields=update_fields)

        return Response({'message': 'Match game uploaded successfully.'})
