from rest_framework import serializers, viewsets
from rest_framework.routers import DefaultRouter

from sandbox.models import Book


class BookSerializer(serializers.ModelSerializer):
    # TODO 1: replace `pass` with a class Meta: model = Book, and fields
    #         id, title, author and published_year
    pass


class BookViewSet(viewsets.ModelViewSet):
    # TODO 2: replace `pass` with `queryset` (all books ordered by id)
    #         and `serializer_class` (BookSerializer, without brackets)
    pass


# TODO 3: make `router = DefaultRouter()` and register BookViewSet at "books"
#         with basename="book"
# TODO 4: set urlpatterns to the router's URLs (router.urls)
urlpatterns = []
