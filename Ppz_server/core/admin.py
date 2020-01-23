from django.contrib import admin
from .models import User, MatchGame, TrainingRun, Network


admin.site.register(User, admin.ModelAdmin)
admin.site.register(MatchGame, admin.ModelAdmin)
admin.site.register(TrainingRun, admin.ModelAdmin)
admin.site.register(Network, admin.ModelAdmin)
