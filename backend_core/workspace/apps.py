from django.apps import AppConfig

class WorkspaceConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'workspace'

    def ready(self):
        # This registers our automatic triggers
        import workspace.signals