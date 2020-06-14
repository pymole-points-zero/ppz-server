# cloud upload
from django.conf import settings
import glob
import os


def upload_examples():
    chunks = glob.glob(os.path.join(settings.TRAINING_EXAMPLES_PATH, '*', '*.tar.gz'), recursive=True)
    for chunk_path in chunks:
        key = os.path.relpath(chunk_path, settings.TRAINING_EXAMPLES_PATH)
        print(key)
        # settings.S3.upload_file(chunk_path, settings.S3_EXAMPLES_BUCKET_NAME, key)
        print(chunk_path, 'uploaded to S3')

    for chunk_path in chunks:
        os.remove(chunk_path)
        print(chunk_path, 'deleted from file system')

