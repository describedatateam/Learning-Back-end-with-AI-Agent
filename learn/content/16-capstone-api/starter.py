from rest_framework import serializers, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.routers import DefaultRouter

from sandbox.models import Task


class TaskSerializer(serializers.ModelSerializer):
    # TODO 1: add a read-only `owner` field that shows the owner's username
    #         (a ReadOnlyField whose source goes from owner to username)

    class Meta:
        model = Task
        fields = ["id", "title", "done"]  # TODO 2: add "owner" to this list


class TaskViewSet(viewsets.ModelViewSet):
    serializer_class = TaskSerializer
    queryset = Task.objects.all()  # Wide open: everyone sees everything! See TODO 4.

    # TODO 3: permission_classes = [IsAuthenticated]
    # TODO 4: replace the queryset line above with a get_queryset(self) method that
    #         returns only self.request.user's tasks, ordered by "id"
    # TODO 6: perform_create(self, serializer): save with owner=self.request.user


router = DefaultRouter()
# TODO 5: register TaskViewSet at "tasks" with basename="task"
urlpatterns = router.urls
