from core.models import Match, MatchGame, Network
from django.conf import settings
from django.db import transaction
import os
from unisgf import Collection, Parser, Renderer


# TODO https://docs.djangoproject.com/en/3.0/topics/db/optimization/

def compute_elo(first_rating, second_rating, first_actual_score):
    # compute elo
    E = lambda ra, rb: 1 / (1 + 10 ** ((ra - rb) / 400))
    D = lambda s, e: 20 * (s - e)

    second_actual_score = 1 - first_actual_score

    expected_result = E(first_rating, second_rating)
    first_diff = D(first_actual_score, expected_result)
    second_diff = D(second_actual_score, expected_result)

    return first_diff, second_diff


def update_elo():
    '''
    Reconstructs SGF files and computes elo.
    :return:
    '''
    parser = Parser()
    renderer = Renderer()
    # get only matches that have all games done
    # TODO add field that tracks computed matches to prevent additional db queries
    matches = Match.objects.filter(done=True).order_by('id').values(
        'id', 'candidate_id', 'current_best_id', 'training_run_id').all()

    networks = Network.objects.filter(
        training_run_id__in=[match['training_run_id'] for match in matches]).values_list('id', 'elo').all()

    networks_elo = {network_id: network_elo for network_id, network_elo in networks}
    update_networks = set()

    for match in matches:
        filename = os.path.join(str(match['training_run_id']), str(match['id']) + '.sgf')
        filepath = os.path.join(settings.MATCH_COLLECTION_SGF_PATH, filename)

        if os.path.exists(filepath):
            continue

        # construct collection of multiple games
        full_collection = Collection()

        candidate_id = match['candidate_id']
        current_best_id = match['current_best_id']

        # it was first match of candidate network. Assign its elo to best elo.
        if networks_elo[candidate_id] == 0:
            networks_elo[candidate_id] = networks_elo[current_best_id]

        match_games = MatchGame.objects.filter(match_id=match['id'], done=True).values_list(
            'id', 'candidate_turns_first').all()

        # each match game changes elo
        for match_game_id, candidate_turns_first in match_games:
            sgf_path = os.path.join(settings.MATCH_SGF_PATH, str(match['id']), str(match_game_id) + '.sgf')
            with open(sgf_path, 'r') as f:
                match_sgf = f.read()

            try:
                collection = parser.parse_string(match_sgf)
            except SyntaxError:
                continue

            game_tree = collection[0]
            root = game_tree.get_root()

            # extract result of the game
            result = str(root['RE'].values[0])
            if result[0] == 'B':
                candidate_score = 0
            elif result[0] == 'W':
                candidate_score = 1
            else:
                candidate_score = 0.5

            if candidate_turns_first:
                candidate_score = 1 - candidate_score

            # compute elo differences
            candidate_diff, current_best_diff = compute_elo(networks_elo[candidate_id], networks_elo[current_best_id],
                                                            candidate_score)

            print(f'{result} {candidate_score}, {candidate_diff}, {current_best_diff}')

            # update only candidate elo
            update_networks.add(candidate_id)
            networks_elo[current_best_id] += current_best_diff
            networks_elo[candidate_id] += candidate_diff

            # TODO make some game tree checks; date, players and source link inserts
            full_collection += collection

        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        renderer.render_file(filepath, full_collection)

    # update when all ratings recalculated
    with transaction.atomic():
        for network_id in update_networks:
            Network.objects.filter(id=network_id).update(elo=networks_elo[network_id])
