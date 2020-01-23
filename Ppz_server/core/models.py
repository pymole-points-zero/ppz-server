from django.db import models
from django.contrib.auth.models import (
    AbstractBaseUser,
    BaseUserManager,
    PermissionsMixin
)
from django.utils import timezone
from rest_framework.exceptions import ValidationError


# описывает редактирование объектов модели
class CustomUserManager(BaseUserManager):
    def create_user(self, login, password, commit=True):
        if not login:
            raise ValidationError({'message': 'User must have a login.'})
        if not password:
            raise ValidationError({'message': 'User must have a password.'})

        user = self.model(login=login)
        user.set_password(password)

        # нужен для исключения повторного коммита в бд при создании суперюзера
        if commit:
            user.save()

        return user

    def create_superuser(self, login, password):
        user = self.create_user(login, password, commit=False)
        user.is_superuser = True
        user.is_staff = True

        user.save()
        return user


# Create your models here.
class User(AbstractBaseUser, PermissionsMixin):
    login = models.CharField(max_length=64, unique=True, null=False)
    password = models.CharField(max_length=64)

    is_staff = models.BooleanField(default=False)

    assigned_training_run = models.ForeignKey('TrainingRun', on_delete=models.SET_NULL, null=True)

    date_joined = models.DateTimeField(default=timezone.now)

    USERNAME_FIELD = 'login'
    REQUIRED_FIELDS = []    # пароль обрабатывается формой, USERNAME_FIELD включать не нужно

    objects = CustomUserManager()

    def __str__(self):
        return self.login


class Network(models.Model):
    created_at = models.DateTimeField(default=timezone.now)

    sha = models.CharField(max_length=64, null=True)
    network_number = models.IntegerField(null=True)
    training_run = models.ForeignKey('TrainingRun', related_name='networks', on_delete=models.SET_NULL, null=True)

    file = models.FileField(upload_to='networks/')
    elo = models.FloatField(default=1600.0)

    # cached because of expensive COUNT(*) call
    games_played = models.IntegerField(default=0)

    layers = models.IntegerField(default=0)
    filters = models.IntegerField(default=0)


class TrainingRun(models.Model):
    best_network = models.ForeignKey(Network, related_name='+', on_delete=models.SET_NULL, null=True, blank=True)

    description = models.TextField(blank=False)
    training_parameters = models.TextField(blank=False)
    active = models.BooleanField(default=False)

    last_game = models.IntegerField(default=0)
    last_network = models.IntegerField(default=0)

    def __str__(self):
        return f'TrainingRun {self.id}'


class TrainingGame(models.Model):
    created_at = models.DateTimeField(default=timezone.now)

    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    training_run = models.ForeignKey(TrainingRun, on_delete=models.SET_NULL, null=True)
    network = models.ForeignKey(Network, on_delete=models.SET_NULL, null=True)

    # TODO сделать директорию загрузки динамической за счет использования функции
    # TODO Make a storage object
    file = models.FileField(upload_to='training_games/')


class Match(models.Model):
    training_run = models.ForeignKey(TrainingRun, related_name='matches', on_delete=models.SET_NULL, null=True)
    parameters = models.TextField()

    candidate = models.ForeignKey(Network, related_name='+', on_delete=models.SET_NULL, null=True)
    current_best = models.ForeignKey(Network, related_name='+', on_delete=models.SET_NULL, null=True)

    games_created = models.IntegerField(default=0)

    wins = models.IntegerField(default=0)
    losses = models.IntegerField(default=0)
    draws = models.IntegerField(default=0)

    finish_games_count = models.IntegerField(null=False)
    done = models.BooleanField(default=False)
    passed = models.BooleanField(null=True)


class MatchGame(models.Model):
    created_at = models.DateTimeField(default=timezone.now)

    user = models.ForeignKey(User, related_name='match_games', on_delete=models.SET_NULL, null=True)
    match = models.ForeignKey(Match, related_name='games', on_delete=models.SET_NULL, null=True)

    file = models.FileField(upload_to='match_games/')
    done = models.BooleanField(default=False)
    result = models.IntegerField(null=True)

