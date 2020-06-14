# TODO compact examples in tar.gz
from django.conf import settings
from django.db import transaction
from core.models import TrainingGame
import os
from collections import defaultdict
import tarfile
from itertools import islice, chain


def compact_examples():
    training_games = TrainingGame.objects.filter(compacted=False).values_list(
        'id', 'game_number', 'training_run_id').order_by('id').all()

    # sort games by training runs
    games_numbers = defaultdict(list)
    games_ids = defaultdict(list)
    for game_id, game_number, training_run_id in training_games:
        games_numbers[training_run_id].append(game_number)
        games_ids[training_run_id].append(game_id)

    for training_run_id in list(games_ids.keys()):
        ids = games_ids[training_run_id]
        if len(ids) < settings.TRAINING_CHUNK_SIZE:
            print(f"Not enough games at training run {training_run_id}")
            games_ids.pop(training_run_id)
            continue

        # trim excess games
        numbers = games_numbers[training_run_id]
        stop = len(numbers)//settings.TRAINING_CHUNK_SIZE * settings.TRAINING_CHUNK_SIZE
        games_ids[training_run_id] = ids[:stop]

        # compact games in .tar.gz
        training_run_path = os.path.join(settings.TRAINING_EXAMPLES_PATH, str(training_run_id))
        for chunk_idx in range(0, len(numbers), settings.TRAINING_CHUNK_SIZE):
            first_game_number = numbers[chunk_idx]
            output_path = os.path.join(training_run_path, str(first_game_number) + '.tar.gz')
            with tarfile.open(output_path, 'w:gz') as tar:
                for game_number in islice(numbers, chunk_idx, chunk_idx + settings.TRAINING_CHUNK_SIZE, 1):
                    game_path = os.path.join(training_run_path, str(game_number) + '.gz')
                    tar.add(game_path)

    #
    # with transaction.atomic():
    #     for id in chain.from_iterable(games_ids.values()):
    #         TrainingGame.objects.filter(id=id).update(compacted=True)

