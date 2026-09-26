from rest_framework.permissions import SAFE_METHODS, BasePermission


class IsOwnerOrReadOnly(BasePermission):
    def has_permission(self, request, view):
        # TODO 1: return True only for logged-in users (request.user.is_authenticated)
        return True

    def has_object_permission(self, request, view, obj):
        # TODO 2: if request.method is in SAFE_METHODS, return True (anyone may read)
        # TODO 3: otherwise return whether obj.owner is the same user as request.user
        return True


class IsStaffForDelete(BasePermission):
    def has_permission(self, request, view):
        # TODO 4: for "DELETE", return request.user.is_staff; for anything else, True
        return True
