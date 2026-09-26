import os

from django.core.exceptions import ImproperlyConfigured


# TODO 1: in every helper, read the value with os.environ.get(name).
#         None or only spaces counts as "missing"; otherwise use value.strip().


def env_str(name, default=None):
    # TODO 2: if the value is there, return it stripped
    # TODO 3: if missing, return default; if default is None, raise
    #         ImproperlyConfigured with a message that contains `name`
    return os.environ.get(name, default)


def env_bool(name, default=False):
    # Bug on purpose: bool("False") is True, because "False" is a non-empty string!
    # TODO 4: missing -> default; lower-case the value, then
    #         1/true/yes/on -> True, 0/false/no/off -> False,
    #         anything else -> raise ImproperlyConfigured
    return bool(os.environ.get(name, default))


def env_int(name, default):
    # TODO 5: missing -> default; otherwise int(value) inside try/except ValueError,
    #         and raise ImproperlyConfigured when it isn't a number
    return int(os.environ.get(name, default))


def env_list(name, default=None):
    # TODO 6: missing -> default, or [] if default is None
    # TODO 7: split at commas, strip each item and skip the empty ones
    return os.environ.get(name, "").split(",")
