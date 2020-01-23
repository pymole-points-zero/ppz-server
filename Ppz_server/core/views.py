from rest_framework.views import APIView
from rest_framework.generics import CreateAPIView
from rest_framework.response import Response
from .models import TrainingGame, User, Match, MatchGame, TrainingRun, Network
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import MultiPartParser, FormParser
from django.core.files import File
import gzip
import hashlib
from django.conf import settings
from django.http import FileResponse
from django.core.exceptions import ObjectDoesNotExist


def check_user(request):
    login = request.data.get('login', None)
    if not login:
        raise ValidationError({'message': 'User must have a login.'})

    user = User.objects.filter(login=login).first()
    if user:
        return user

    user = User.objects.create_user(**request.data, commit=False)
    return user


class NextGameView(APIView):
    def post(self, request, *args, **kwargs):
        user = check_user(request)
        training_run = TrainingGame.objects.order_by('?').first()

        user.assigned_training_run = training_run
        user.save(update_fields=['assigned_training_run'])

        match = Match.objects.filter(training_run=training_run, done=False).first()

        if match:
            match_game = MatchGame.objects.create(user=user, match=match)
            result = {
                'type': 'match',
                'match_game_id': match_game.id,
                'best_sha': match.current_best.sha,
                'candidate_sha': match.candidate.sha,
                'parameters': match.parameters,
            }

            return Response(result)

        result = {
            "type": "train",
            "training_run_id": training_run.id,
            "network_id": training_run.best_network.id,
            "sha": training_run.best_network.Sha,
            "params": training_run.train_parameters,
            "keep_time": "16h",
        }

        return Response(result)


class UploadNetworkView(APIView):
    parser_classes = [MultiPartParser]

    def post(self, request):
        new_network_file = request.FILES.get('network', None)
        if new_network_file is None:
            raise ValidationError({'message': 'Need network file.'})

        prev_network_sha = request.data.get('prev_delta_sha', None)
        if prev_network_sha is not None:
            prev_network = Network.objects.filter(sha=prev_network_sha).first()

            if prev_network is None:
                raise ValidationError({'message': 'Unknown previous network'})

            try:
                prevData = gzip.open(prev_network.file.name).read()
            except OSError:
                raise ValidationError({'message': 'Corrupted previous network.'})

            deltaData = gzip.decompress(new_network_file.read())
            if len(prevData) != len(deltaData):
                return ValidationError({'message': "Data lengths don' match."})

            changes = bytes(p ^ d for d, p in zip(deltaData, prevData))

            sha = hashlib.sha256(changes).hexdigest()
        else:
            sha = hashlib.sha256(gzip.decompress(new_network_file.read())).hexdigest()

        if Network.objects.filter(sha=sha).exists():
            raise ValidationError({'message': "Network exists."})

        training_run_id = int(request.data.get('training_run_id', 0))

        training_run = TrainingRun.objects.select_related('best_network').filter(id=training_run_id).first()
        if training_run is None:
            raise ValidationError({'message': "Training run does not exists."})

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
              params=settings.MATCHES.get('params'))

        # reggression check
        prev_network1 = training_run.networks.filter(network_number=training_run.last_network - 3).first()
        if prev_network1 is not None:
            Match.objects.create(training_run=training_run, candidate=prev_network1, current_best=best_network,
                             params=settings.MATCHES.get('params'))

        prev_network2 = training_run.networks.filter(network_number=training_run.last_network - 10).first()
        if prev_network2 is not None:
            Match.objects.create(training_run=training_run, candidate=prev_network2, current_best=best_network,
                             params=settings.MATCHES.get('params'))

        return Response({'message': 'Network uploaded successfully.'})


class UploadGameView(APIView):
    parser_classes = [FormParser]

    def post(self, request):
        user = check_user(request)
        game_file = request.FILES.get('game_file', None)

        if game_file is None:
            raise ValidationError({'message': 'No file.'})

        if game_file.size <= 0:
            raise ValidationError({'message': 'Empty file.'})

        training_run_id = request.data.get('training_run_id', None)
        if training_run_id is None:
            raise ValidationError({'message': 'No training run id.'})

        try:
            training_run_id = int(training_run_id)
        except ValueError:
            raise ValidationError({'message': 'Training run id need to be an integer.'})

        try:
            training_run = TrainingRun.object.get(training_run_id)
        except ObjectDoesNotExist:
            raise ValidationError({'message': 'Invalid training id.'})

        network_id = request.data.get('network_id', None)
        if network_id is None:
            raise ValidationError({'message': 'Provide network id.'})

        try:
            network_id = int(network_id)
        except ValueError:
            raise ValidationError({'message': 'Network id need to be an integer.'})

        try:
            network = Network.object.get(network_id)
        except ObjectDoesNotExist:
            raise ValidationError({'message': 'Invalid network id.'})

        network.games_played += 1
        network.save(update_fields=['games_played'])

        training_run.last_game += 1
        training_run.save(update_fields=['last_game'])

        training_game = TrainingGame.objects.create(user=user, training_run=training_run, network=network,
                                     game_number=training_run.last_game)

        training_game.file.save(f'{training_run_id}_{training_game.game_number}', game_file.read())

        return Response({'message': 'Training game uploaded successfully.'})


class DownloadNetworkView(APIView):
    def get(self, request):
        sha = request.data.get('sha', None)
        if sha is None:
            raise ValidationError({'message': 'No sha.'})

        network = Network.objects.filter(sha=sha).first()
        if network is None:
            raise ValidationError({'message': 'Invalid sha.'})

        network.file.open()
        return FileResponse(network.file, filename=network.file.name)


class MatchResultView(APIView):
    parser_classes = [FormParser]

    def post(self, request):
        match_game_file = request.data.get('match_game_file', None)
        if match_game_file is None:
            raise ValidationError({'message': 'No match game file.'})

        match_game_id = request.data.get('match_game_id', None)

        if match_game_id is None:
            raise ValidationError({'message': 'No match game id.'})

        try:
            match_game_id = int(match_game_id)
        except ValueError:
            raise ValidationError({'message': 'Match game id need to be an integer.'})

        match_game = MatchGame.objects.select_related('match').filter(id=match_game_id).first()
        if match_game is None:
            raise ValidationError({'message': 'Invalid match game.'})

        result = request.data.get('result', None)

        if result is None:
            raise ValidationError({'message': 'No result.'})

        try:
            result = int(result)
        except ValueError:
            raise ValidationError({'message': 'Result need to be an integer.'})

        match = match_game.match
        if result == 0:
            match.draws += 1
            update_fields = ['draws']
        elif result == -1:
            match.losses += 1
            update_fields = ['losses']
        elif result == 1:
            match.wins += 1
            update_fields = ['wins']
        else:
            raise ValidationError({'message': 'Bad result.'})

        match_game.result = result
        match_game.done = True
        match_game.file.save(str(match_game_id), match_game_file.read())

        match_game.save(update_fields=['result', 'done'])

        if match.done:
            raise ValidationError({'message': 'Match already is done.'})

        games_count = match.wins + match.losses + match.draws

        if games_count >= match.finish_games_count:
            match.done = True

            w = match.wins/games_count
            d = match.draws/games_count

            mu = w + d/2

            passed = mu >= settings.MATCHES['update_threshold']

            # TODO Не понятно, где изменяется эло

            match.passed = passed

            if passed:
                match.training_run.best_network = match.candidate
                match.training_run.save(update_fields='best_network')

            update_fields += ['done', 'passed']

        match.save(update_fields=update_fields)
