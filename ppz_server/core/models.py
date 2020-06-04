from django.db import models
from django.contrib.auth.models import (
    AbstractBaseUser,
    BaseUserManager,
    PermissionsMixin
)
from django.contrib.postgres.fields import JSONField
from django.utils import timezone
from rest_framework.exceptions import ValidationError


# описывает редактирование объектов модели
class CustomUserManager(BaseUserManager):
    def create_user(self, username, password, commit=True):
        if not username:
            raise ValidationError({'error': 'User must have a username.'})
        if not password:
            raise ValidationError({'error': 'User must have a password.'})

        user = self.model(username=username)
        user.set_password(password)

        # нужен для исключения повторного коммита в бд при создании суперюзера
        if commit:
            user.save()

        return user

    def create_superuser(self, username, password):
        user = self.create_user(username, password, commit=False)
        user.is_superuser = True
        user.is_staff = True

        user.save()
        return user


# Create your models here.
class User(AbstractBaseUser, PermissionsMixin):
    username = models.CharField(max_length=64, unique=True)

    is_staff = models.BooleanField(default=False)

    assigned_training_run = models.ForeignKey('TrainingRun', on_delete=models.SET_NULL, null=True)

    date_joined = models.DateTimeField(default=timezone.now)

    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = []    # пароль обрабатывается формой, USERNAME_FIELD включать не нужно

    objects = CustomUserManager()

    def __str__(self):
        return self.username


class Network(models.Model):
    created_at = models.DateTimeField(default=timezone.now)

    sha = models.CharField(max_length=64, null=True)
    network_number = models.IntegerField()
    training_run = models.ForeignKey('TrainingRun', related_name='networks', on_delete=models.SET_NULL, null=True)

    file = models.FileField(upload_to='networks/')

    elo = models.FloatField(default=0.0)

    # cached because of expensive COUNT(*) call
    games_played = models.IntegerField(default=0)

    blocks = models.IntegerField(default=0)
    filters = models.IntegerField(default=0)
    field_width = models.IntegerField()
    field_height = models.IntegerField()


class TrainingRun(models.Model):
    best_network = models.ForeignKey(Network, related_name='+', on_delete=models.SET_NULL, null=True, blank=True)

    field_width = models.IntegerField()
    field_height = models.IntegerField()

    description = models.TextField(blank=True, null=True)
    training_parameters = JSONField(blank=True)
    match_parameters = JSONField(blank=True)

    active = models.BooleanField(default=False)

    last_game = models.IntegerField(default=0)
    last_network = models.IntegerField(default=0)

    def __str__(self):
        return f'TrainingRun {self.id}'


class TrainingGame(models.Model):
    created_at = models.DateTimeField(default=timezone.now)
    game_number = models.IntegerField()

    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    training_run = models.ForeignKey(TrainingRun, on_delete=models.SET_NULL, null=True)
    network = models.ForeignKey(Network, on_delete=models.SET_NULL, null=True)

    compacted = models.BooleanField(default=False)


class Match(models.Model):
    training_run = models.ForeignKey(TrainingRun, related_name='matches', on_delete=models.SET_NULL, null=True)
    parameters = JSONField(blank=True)

    candidate = models.ForeignKey(Network, related_name='+', on_delete=models.SET_NULL, null=True)
    current_best = models.ForeignKey(Network, related_name='+', on_delete=models.SET_NULL, null=True)

    # TODO зачем это поле?
    games_created = models.IntegerField(default=0)

    candidate_wins = models.IntegerField(default=0)
    best_wins= models.IntegerField(default=0)
    draws = models.IntegerField(default=0)

    games_to_finish = models.IntegerField()
    done = models.BooleanField(default=False)
    passed = models.BooleanField(null=True)

    created_at = models.DateTimeField(default=timezone.now)


class MatchGame(models.Model):
    created_at = models.DateTimeField(default=timezone.now)

    user = models.ForeignKey(User, related_name='match_games', on_delete=models.SET_NULL, null=True)
    match = models.ForeignKey(Match, related_name='games', on_delete=models.SET_NULL, null=True)

    # null = True because value calculated from id that appears after creation
    candidate_turns_first = models.BooleanField(null=True)

    result = models.IntegerField(null=True)
    done = models.BooleanField(default=False)

