from rest_framework import serializers, viewsets
from rest_framework.routers import DefaultRouter

from sandbox.models import Book


class BookSerializer(serializers.ModelSerializer):
    class Meta:
        model = Book
        fields = ["id", "title", "author", "published_year"]


class BookViewSet(viewsets.ModelViewSet):
    queryset = Book.objects.order_by("id")
    serializer_class = BookSerializer


router = DefaultRouter()
router.register("books", BookViewSet, basename="book")
urlpatterns = router.urls
