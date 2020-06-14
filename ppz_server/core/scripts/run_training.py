import subprocess
from django.conf import settings
from django.db.models import F
from core.models import Network
import os
import json


def run_training():
    # start training for a training run in which training
    # has not been carried out for the longest time

    training_run_id, best_sha, blocks, filters, width, height = Network.objects.filter(
        training_run__active=True,
        network_number=F('training_run__last_network')
    ).order_by('created_at').values_list(
        'training_run_id', 'training_run__best_network__sha', 'training_run__best_network__blocks',
        'training_run__best_network__filters', 'training_run__field_width',
        'training_run__field_height'
    ).first()

    # print(training_run_id, best_sha, width, height, blocks, filters)

    # construct new config
    base_training_config = os.path.join(settings.BASE_DIR, 'ppz_server',
                                        'configs', 'base_training_config.json')
    with open(base_training_config, 'r') as f:
        config = json.load(f)

    config["input_path"] = os.path.join(settings.TRAINING_EXAMPLES_PATH, str(training_run_id))
    config["model_input"] = os.path.join(settings.NETWORKS_PATH, best_sha+'.gz')
    config["upload"]["params"] = {
        "blocks": blocks,
        "filters": filters,
        "field_width": width,
        "field_height": height,
        "training_run_id": training_run_id,
        "prev_delta_sha": best_sha
    }

    print(config)

    config_path = os.path.join(settings.TRAINING_PATH, 'configs', 'config.json')
    with open(config_path, 'w') as f:
        json.dump(config, f)

    command_args = [
        os.path.join(settings.TRAINING_PATH, 'venv', 'bin', 'python3.8'),
        os.path.join(settings.TRAINING_PATH, 'train.py'),
        '--config', config_path,
    ]

    command_string = ' '.join(command_args)
    training_process = subprocess.Popen(command_string, shell=True)
    training_process.wait()


