import json

from django.conf import settings
from django.core.exceptions import PermissionDenied

try:
    from django.core import urlresolvers
except ImportError:
    from django import urls as urlresolvers
try:
    from django.urls.exceptions import NoReverseMatch
except ImportError:
    from django.core.urlresolvers import NoReverseMatch
from django.utils.html import format_html
from django.utils.safestring import mark_safe

MAX = 75


class ReadOnlyAdminMixin(object):
    """
    Disables all editing capabilities.
    """

    # read only template
    change_form_template = "admin/view_only.html"

    def get_actions(self, request):
        actions = super(ReadOnlyAdminMixin, self).get_actions(request)
        del actions["delete_selected"]
        return actions

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        pass

    def delete_model(self, request, obj):
        raise PermissionDenied(_('log entries must not be modified.'))

    def save_related(self, request, form, formsets, change):
        pass


class LogEntryAdminMixin(object):

    def created(self, obj):
        return obj.timestamp.strftime('%Y-%m-%d %H:%M:%S')
    created.short_description = 'Created'

    def user_url(self, obj):
        if obj.actor:
            app_label, model = settings.AUTH_USER_MODEL.split('.')
            viewname = 'admin:%s_%s_change' % (app_label, model.lower())
            try:
                link = urlresolvers.reverse(viewname, args=[obj.actor.id])
            except NoReverseMatch:
                return mark_safe(
                    u'%s' % (obj.actor)
                )
            return mark_safe(format_html(
                u'<a href="{}">{}</a>', link, obj.actor
            ))

        return 'system'
    user_url.short_description = 'User'

    def resource_url(self, obj):
        app_label, model = obj.content_type.app_label, obj.content_type.model
        viewname = 'admin:%s_%s_change' % (app_label, model)
        try:
            args = [obj.object_pk] if obj.object_id is None else [obj.object_id]
            link = urlresolvers.reverse(viewname, args=args)
        except NoReverseMatch:
            return mark_safe(obj.object_repr)
        else:
            return mark_safe(format_html(
                u'<a href="{}">{}</a>', link, obj.object_repr
            ))
    resource_url.short_description = 'Resource'

    def msg_short(self, obj):
        if obj.action == 2:
            return ''  # delete
        changes = json.loads(obj.changes)
        s = '' if len(changes) == 1 else 's'
        fields = ', '.join(changes.keys())
        if len(fields) > MAX:
            i = fields.rfind(' ', 0, MAX)
            fields = fields[:i] + ' ..'
        return '%d change%s: %s' % (len(changes), s, fields)
    msg_short.short_description = 'Changes'

    def msg(self, obj):
        if obj.action == 2:
            return ''  # delete
        changes = json.loads(obj.changes)
        msg = '<table><tr><th>#</th><th>Field</th><th>From</th><th>To</th></tr>'
        for i, field in enumerate(sorted(changes), 1):
            value = [i, field] + (['***', '***'] if field == 'password' else changes[field])
            msg += format_html('<tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>', *value)

        msg += '</table>'
        return mark_safe(msg)
    msg.short_description = 'Changes'

    def action_name(self, inst, *args, **kwargs):
        description = str(inst)
        action_parts = description.split(' ')

        return "{action_name} {on_model}: {description}".format(
            action_name=action_parts[0],
            on_model=str(self.model.__name__).split('.')[-1],
            description=" ".join(action_parts[1:]),
        )
