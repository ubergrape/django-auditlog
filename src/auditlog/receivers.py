from __future__ import unicode_literals

import json

from auditlog.diff import model_instance_diff
from auditlog.models import LogEntry
import logging

logger = logging.get_logger(__name__)


def create_log(instance, action, changes):
    try:
        return LogEntry.objects.log_create(
            instance, action=action, changes=changes
        )
    except Excetion as ex:
        logger.error(
            'Error saving aduitlog for models %s: %s',
            instance, ex
        )


def get_diff(m1, m2):
    try:
        return model_instance_diff(m1, m2)
    except Excetion as ex:
        logger.error(
            'Error getting diff between models %s for aduitlog: %s',
            m1 or m2, ex
        )


def log_create(sender, instance, created, **kwargs):
    """
    Signal receiver that creates a log entry when a model instance is first saved to the database.

    Direct use is discouraged, connect your model through :py:func:`auditlog.registry.register` instead.
    """
    if created:
        return create_log(
            instance,
            action=LogEntry.Action.CREATE,
            changes=json.dumps(get_diff(None, instance))
        )


def log_update(sender, instance, **kwargs):
    """
    Signal receiver that creates a log entry when a model instance is changed and saved to the database.

    Direct use is discouraged, connect your model through :py:func:`auditlog.registry.register` instead.
    """
    if instance.pk is not None:
        try:
            old = sender.objects.get(pk=instance.pk)
        except sender.DoesNotExist:
            pass
        else:
            new = instance

            changes = get_diff(old, new)
            # Log an entry only if there are changes
            if changes:
                return create_log(
                    instance,
                    action=LogEntry.Action.UPDATE,
                    changes=json.dumps(changes),
                )


def log_delete(sender, instance, **kwargs):
    """
    Signal receiver that creates a log entry when a model instance is deleted from the database.

    Direct use is discouraged, connect your model through :py:func:`auditlog.registry.register` instead.
    """
    if instance.pk is not None:
        return create_log(
            instance,
            action=LogEntry.Action.DELETE,
            changes=json.dumps(get_diff(instance, None))
        )
