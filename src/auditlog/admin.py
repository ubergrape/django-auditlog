from auditlog.filters import ResourceTypeFilter
from auditlog.mixins import LogEntryAdminMixin, ReadOnlyAdminMixin
from django.urls import reverse
from django.utils.translation import ugettext_lazy as _
from auditlog.models import LogEntry
from auditlog.registry import auditlog as auditlog_registry
from django.contrib import admin
from django.contrib.admin.utils import unquote
from django.core.exceptions import PermissionDenied
from django.template.response import TemplateResponse
from django.utils.safestring import mark_safe
from django.utils.text import capfirst
from django.utils.translation import gettext as _


class LogEntryAdmin(ReadOnlyAdminMixin, LogEntryAdminMixin, admin.ModelAdmin):
    list_display = [
        'created', 'resource_url', 'action', 'msg_short', 'user_url'
    ]
    search_fields = [
        'timestamp', 'object_repr', 'changes', 'actor__first_name',
        'actor__last_name', 'actor__email', 'remote_addr', 'additional_data'
    ]
    readonly_fields = [
        'created', 'resource_url', 'action', 'user_url', 'msg',
        'remote_addr', 'actor'
    ]

    fieldsets = [
        (_('Who'), {'fields': ['user_url', 'remote_addr', 'created']}),
        (_('What'), {'fields': ['resource_url', 'action', 'msg']}),
    ]

    list_filter = ['action', 'actor', ResourceTypeFilter]


class HistoryModelAdmin(LogEntryAdminMixin, admin.ModelAdmin):
    """
    annotate extended log info into the "history" button of every model admin.
    overwrite the history from the normal log to the audit log's model.
    """
    object_history_template = 'admin/extended_object_history.html'

    # fields to in or exclude for audit tracking. either or, not booth
    log_include_fields = None
    log_exclude_fields = None

    def enrich_action_list(self, action_list):
        res = []
        for action in action_list:
            created = self.created(action)
            res.append({
                'remote_addr': action.remote_addr,
                'msg_short': self.msg_short(action),
                'resource_url': self.resource_url(action),
                'actor_url': self.user_url(action),
                'created': created,
                'url': audit_url(action, created),
                'action_name': self.action_name(action),

                # handy extra data to use in custom templates maybe.
                'content_type': action.content_type,
                'object_pk': action.object_pk,
                'object_id': action.object_id,
                'object_repr': action.object_repr,
                'action': action.action,
                'actor': action.actor,
                'timestamp': action.timestamp,
                'additional_data': action.additional_data,
            })
        return res

    def history_view(self, request, object_id, extra_context=None):
        model = self.model
        obj = self.get_object(request, unquote(object_id))
        if obj is None:
            return self._get_obj_does_not_exist_redirect(
                request, model._meta, object_id
            )
        if not self.has_change_permission(request, obj):
            raise PermissionDenied

        opts = model._meta

        request = fix_invalid_filters(request)
        changelist = self.get_changelist_instance(request)
        changelist.queryset = LogEntry.objects.get_for_model(
            self.model).filter(
            object_id=unquote(object_id)
        ).order_by('-timestamp')

        # pagination and stuff
        changelist.model = LogEntry
        changelist.get_results(request)
        enriched_result = self.enrich_action_list(changelist.result_list)

        context = dict(
            self.admin_site.each_context(request),
            title=_('Change history: %(model_name)s') % {'model_name': obj},
            action_list=enriched_result,
            module_name=str(capfirst(opts.verbose_name_plural)),
            object=obj,
            opts=opts,
            preserved_filters=self.get_preserved_filters(request),
            cl=changelist
        )

        context.update(extra_context or {})

        request.current_app = self.admin_site.name

        return TemplateResponse(request, self.object_history_template, context)


def fix_invalid_filters(request, fields=('_changelist_filters',)):
    """
    this method is a workaround for django passing invalid filters to
    models they don't understand but really are into interpreting it.
    its a hack but so is the whole django admin anyway.
    :param request: the request object
    :param fields: fields to be removed
    :return: the fixed request object
    """
    remove = set()
    for field in fields:
        if field in request.GET:
            remove.add(field)

    mutable = request.GET._mutable
    request.GET._mutable = True
    [request.GET.pop(field, None) for field in remove]
    request.GET._mutable = mutable
    return request


def auditlog(*models):
    """
    decorator for registering admin sites to audit logs.
    :param models: django.db.models
    :return: func
    """
    def _model_admin_wrapper(admin_class):
        if not models:
            raise ValueError('At least one model must be passed to register.')
        for model in models:
            if not issubclass(admin_class, HistoryModelAdmin):
                raise ValueError(
                    'Auditlog registered Classes '
                    'must subclass HistoryModelAdmin.'
                )
            auditlog_registry.register(
                model,
                exclude_fields=admin_class.log_exclude_fields,
                include_fields=admin_class.log_include_fields
            )
        return admin_class
    return _model_admin_wrapper


def audit_url(obj, title=None):
    """
    return a relative auditlog URL for an object.
    :param obj: instance of auditlog.LogEntry
    :param title: title of the link
    :return: `str` link containing href
    """
    title = title or repr(obj)
    return mark_safe(
        '<a href="%s">%s</a>' % (
            reverse(
                'admin:auditlog_logentry_change',
                kwargs={'object_id': obj.pk}
            ), title
        )
    )


def add_mixin(klass, *mixins):
    """
    dynamically declare a new class with the name Extended{old_name} and
    return the inherited class object
    :param klass: the class to redeclare with mixins
    :param mixins: the mixins to use
    :return: object class
    """
    new_name = 'Extended{}'.format(klass.__name__)
    return type(new_name, tuple(mixins), {})


def re_register(model, model_admin):
    """
    re-register a already registered modelAdmin for audiotlog and django admin
    by dynamically extending it from HistoryModelAdmin in case it is not yet.
    make sure the auditlog app is the last one in loading order otherwise
    you might experience a race condition for registering admin sites.
    :param model: django.db.models
    :param model_admin: model.admin
    :return: None
    """
    if not isinstance(model_admin, HistoryModelAdmin):
        model_admin = add_mixin(model_admin, HistoryModelAdmin)

    admin.site.unregister(model)
    admin.site.register(model, model_admin)

    auditlog_registry.register(model)


admin.site.register(LogEntry, LogEntryAdmin)
