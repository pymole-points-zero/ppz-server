from rest_framework.views import APIView
from rest_framework.response import Response
from .models import TrainingGame, User, Match, MatchGame, TrainingRun, Network
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import MultiPartParser, JSONParser
import gzip
import hashlib
from django.conf import settings
from django.http import FileResponse, HttpResponseRedirect
from django.core.exceptions import ObjectDoesNotExist
import os

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
            return Response({'error': 'No active training runs.'})

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
                'field_width': training_run.field_width,
                'field_height': training_run.field_height,
                'candidate_turns_first': candidate_turns_first
            }

            return Response(result)

        result = {
            'game_type': 'train',
            'training_run_id': training_run.id,
            'network_id': training_run.best_network.id,
            'best_network_sha': training_run.best_network.sha,
            'parameters': training_run.training_parameters,
            'field_width': training_run.field_width,
            'field_height': training_run.field_height,
            'keep_time': 16,
        }

        return Response(result)


class UploadNetworkView(APIView):
    parser_classes = [MultiPartParser]

    def post(self, request):
        # TODO make upload possible only for admins
        new_network_file = request.FILES.get('network', None)
        if new_network_file is None:
            raise ValidationError({'error': 'Need network file.'})

        # TODO error handle not a gziped file
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
            print(len(prevData), len(deltaData))
            if len(prevData) != len(deltaData):
                raise ValidationError({'error': "Data lengths don't match."})

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
        blocks = request.data.get('blocks', 0)
        # TODO add field size checks
        field_width = request.data.get('field_width', 0)
        field_height = request.data.get('field_height', 0)

        new_network = Network.objects.create(
            training_run=training_run, blocks=blocks, filters=filters, field_width=field_width,
            field_height=field_height, sha=sha, network_number=training_run.last_network
        )

        # save new network file
        if settings.CLOUD_STOREAGE:
            settings.S3.upload_fileobj(new_network_file, settings.S3_NETWORKS_BUCKET_NAME, sha+'.gz')
        else:
            network_path = os.path.join(settings.NETWORKS_PATH, sha + '.gz')
            os.makedirs(os.path.dirname(network_path), exist_ok=True)
            with open(network_path, 'wb') as f:
                f.write(new_network_file.read())

        # create match
        best_network = training_run.best_network
        if best_network is None:
            raise ValidationError({'message': "Uploaded, but no best network."})

        Match.objects.create(training_run=training_run, candidate=new_network, current_best=best_network,
                             parameters=training_run.match_parameters,
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

        training_game_sgf = request.FILES.get('training_game_sgf', None)
        if training_game_sgf is None:
            raise ValidationError({'error': 'Need a training game sgf.'})

        training_example = request.FILES.get('training_example', None)
        if training_example is None:
            raise ValidationError({'error': 'Need a training example.'})

        network.games_played += 1
        network.save(update_fields=['games_played'])
        training_run.last_game += 1
        training_run.save(update_fields=['last_game'])

        training_game = TrainingGame.objects.create(user=user, training_run=training_run,
                                                    network=network, game_number=training_run.last_game)

        # save sgf
        sgf_path = os.path.join(settings.TRAINING_SGF_PATH, str(training_run.id), str(training_run.last_game) + '.sgf')
        os.makedirs(os.path.dirname(sgf_path), exist_ok=True)
        with open(sgf_path, 'wb') as f:
            f.write(training_game_sgf.read())

        # save example
        example_path = os.path.join(settings.TRAINING_EXAMPLES_PATH,
                                    str(training_run.id), str(training_run.last_game) + '.gz')
        os.makedirs(os.path.dirname(example_path), exist_ok=True)
        with open(example_path, 'wb') as f:
            f.write(training_example.read())

        return Response({'message': 'Training game uploaded successfully.'})


class DownloadNetworkView(APIView):
    def get(self, request):
        sha = request.data.get('sha', None)
        if sha is None:
            raise ValidationError({'error': 'No sha.'})

        network = Network.objects.filter(sha=sha).first()
        if network is None:
            raise ValidationError({'error': 'Invalid sha.'})

        filename = sha + '.gz'

        if settings.CLOUD_STORAGE:
            url = settings.S3.generate_presigned_url(
                ClientMethod='get_object',
                Params={
                    'Bucket': settings.S3_NETWORKS_BUCKET_NAME,
                    'Key': filename
                }
            )
            return HttpResponseRedirect(url)

        network_file = open(os.path.join(settings.NETWORKS_PATH, filename), 'rb')
        return FileResponse(network_file, filename=network_file.name)


class UploadMatchGameView(APIView):
    parser_classes = [MultiPartParser]

    def post(self, request):
        user = check_user(request)

        match_game_sgf = request.FILES.get('match_game_sgf', None)
        if match_game_sgf is None:
            raise ValidationError({'error': 'No match game sgf.'})

        match_game_id = request.data.get('match_game_id', None)

        if match_game_id is None:
            raise ValidationError({'error': 'No match game id.'})

        try:
            match_game_id = int(match_game_id)
        except ValueError:
            raise ValidationError({'error': 'Match game id need to be an integer.'})

        match_game = MatchGame.objects.select_related(
            'match', 'match__training_run').filter(id=match_game_id).first()
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

        match_game.save(update_fields=['result', 'done'])

        # save sgf
        sgf_path = os.path.join(settings.MATCH_SGF_PATH, str(match.training_run_id),
                                str(match.id), str(match_game.id) + '.sgf')
        os.makedirs(os.path.dirname(sgf_path), exist_ok=True)

        with open(sgf_path, 'wb') as f:
            f.write(match_game_sgf.read())

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
                match.training_run.save()

            update_fields += ['done', 'passed']

        match.save(update_fields=update_fields)

        return Response({'message': 'Match game uploaded successfully.'})
