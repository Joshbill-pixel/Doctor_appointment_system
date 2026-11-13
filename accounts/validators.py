import re

from django.core.exceptions import ValidationError

PHONE_PATTERN = re.compile(r"^\+?[0-9][0-9\s\-()]{6,18}[0-9]$")


def validate_phone(value):
    """Accepts Nigerian-style numbers such as 08012345678 or +234 801 234 5678."""
    if value and not PHONE_PATTERN.match(value.strip()):
        raise ValidationError("Enter a valid phone number, e.g. 08012345678 or +234 801 234 5678.")
