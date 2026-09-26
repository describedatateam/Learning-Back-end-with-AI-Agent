import os

from django.core.exceptions import ImproperlyConfigured

TRUE_VALUES = {"1", "true", "yes", "on"}
FALSE_VALUES = {"0", "false", "no", "off"}


def _raw(name):
    """The stripped value, or None if unset/blank."""
    value = os.environ.get(name)
    if value is None or not value.strip():
        return None
    return value.strip()


def env_str(name, default=None):
    value = _raw(name)
    if value is not None:
        return value
    if default is None:
        raise ImproperlyConfigured(f"Set the {name} environment variable.")
    return default


def env_bool(name, default=False):
    value = _raw(name)
    if value is None:
        return default
    if value.lower() in TRUE_VALUES:
        return True
    if value.lower() in FALSE_VALUES:
        return False
    raise ImproperlyConfigured(f"{name} must be a boolean (true/false), got {value!r}.")


def env_int(name, default):
    value = _raw(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        raise ImproperlyConfigured(f"{name} must be an integer, got {value!r}.")


def env_list(name, default=None):
    value = _raw(name)
    if value is None:
        return default if default is not None else []
    return [item.strip() for item in value.split(",") if item.strip()]
