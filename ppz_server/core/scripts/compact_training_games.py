from django.conf import settings
from ppz_server.core.models import TrainingGame
import os
import glob


# TODO finish
def compact_games():
    '''
    Compact training games in big archive, delete all games leaving n for training.
    :return:
    '''
    while True:
        training_games = TrainingGame.objects.filter(compacted=False).limit(settings.training_chunk_size).all()
        if len(training_games) != settings.training_chunk_size:
            return

        # limit can take games from another chunk. Need to calculate real border
        stop = (training_games[0].id // settings.training_chunk_size + 1) * settings.training_chunk_size

        for i, training_game in enumerate(training_games):
            if training_game.id >= stop:
                training_games = training_games[:i]
                break

        # archive games
        # os.path.join(settings.training_sgf_path, training_run.id, (training_run.last_game + '.sgf'))





