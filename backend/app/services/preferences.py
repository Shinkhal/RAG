"""Account preference helpers shared by the auth and profile routes."""

from pydantic import ValidationError

from app.db.models import Account
from app.schemas.profile import ProfilePreferences, ProfilePreferencesUpdate

# Fields that always have a value and therefore cannot be cleared with null.
REQUIRED_PREFERENCE_FIELDS = ("theme", "email_notifications")


def current_preferences(account: Account) -> ProfilePreferences:
    """Merge stored preferences over defaults, dropping invalid values.

    Values are validated one field at a time so a single bad entry (for example
    from an older release or a manual database edit) does not reset every other
    preference to its default.
    """
    defaults = ProfilePreferences()
    stored = account.preferences if isinstance(account.preferences, dict) else {}
    values = defaults.model_dump()

    for field in ProfilePreferences.model_fields:
        if field not in stored:
            continue
        try:
            validated = ProfilePreferences.model_validate({**values, field: stored[field]})
        except ValidationError:
            continue
        values[field] = getattr(validated, field)

    return ProfilePreferences.model_validate(values)


def merge_preference_update(
    account: Account, update: ProfilePreferencesUpdate
) -> ProfilePreferences:
    """Apply a partial update without persisting invalid or clearing nulls."""
    changes = update.model_dump(exclude_unset=True)

    # ``theme`` and ``email_notifications`` always have a value. Treat an
    # explicit null as "leave unchanged", while ``default_persona_id`` can be
    # cleared by sending null.
    for field in REQUIRED_PREFERENCE_FIELDS:
        if changes.get(field) is None:
            changes.pop(field, None)

    preferences = current_preferences(account).model_dump()
    preferences.update(changes)
    return ProfilePreferences.model_validate(preferences)
