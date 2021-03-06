import locale

import django

from django.conf import settings
from django.contrib.admin.templatetags.admin_static import static
from django.core.urlresolvers import reverse
from django.forms.widgets import Select
from django.utils.safestring import mark_safe
from django.utils.encoding import force_text

from smart_selects.utils import unicode_sorter, sort_results

try:
    from django.apps import apps
    get_model = apps.get_model
except ImportError:
    from django.db.models.loading import get_model


if django.VERSION >= (1, 2, 0) and getattr(settings,
                                           'USE_DJANGO_JQUERY', True):
    USE_DJANGO_JQUERY = True
else:
    USE_DJANGO_JQUERY = False
    JQUERY_URL = getattr(settings, 'JQUERY_URL', 'http://ajax.googleapis.com/ajax/libs/jquery/1.3.2/jquery.min.js')

URL_PREFIX = getattr(settings, "SMART_SELECTS_URL_PREFIX", "")


class ChainedSelect(Select):
    def __init__(self, app_name, model_name, chain_field, model_field,
                 foreign_key_app_name, foreign_key_model_name, foreign_key_field_name,
                 show_all, auto_choose, manager=None, view_name=None, *args, **kwargs):
        self.app_name = app_name
        self.model_name = model_name
        self.chain_field = chain_field
        self.model_field = model_field
        self.show_all = show_all
        self.auto_choose = auto_choose
        self.manager = manager
        self.view_name = view_name
        self.foreign_key_app_name = foreign_key_app_name
        self.foreign_key_model_name = foreign_key_model_name
        self.foreign_key_field_name = foreign_key_field_name
        super(Select, self).__init__(*args, **kwargs)

    class Media:
        extra = '' if settings.DEBUG else '.min'
        js = [
            'jquery%s.js' % extra,
            'jquery.init.js'
        ]
        if USE_DJANGO_JQUERY:
            js = [static('admin/js/%s' % url) for url in js]
        elif JQUERY_URL:
            js = [JQUERY_URL]
        js.append(static("smart_selects/js/chained.js"))

    def render(self, name, value, attrs=None, choices=()):
        if len(name.split('-')) > 1:  # formset
            chain_field = '-'.join(name.split('-')[:-1] + [self.chain_field])
        else:
            chain_field = self.chain_field
        if not self.view_name:
            if self.show_all:
                view_name = "chained_filter_all"
            else:
                view_name = "chained_filter"
        else:
            view_name = self.view_name
        kwargs = {
            'app': self.app_name,
            'model': self.model_name,
            'field': self.model_field,
            'foreign_key_app_name': self.foreign_key_app_name,
            'foreign_key_model_name': self.foreign_key_model_name,
            'foreign_key_field_name': self.foreign_key_field_name,
            'value': '1'
            }
        if self.manager is not None:
            kwargs.update({'manager': self.manager})
        url = URL_PREFIX + ("/".join(reverse(view_name, kwargs=kwargs).split("/")[:-2]))
        if self.auto_choose:
            auto_choose = 'true'
        else:
            auto_choose = 'false'
        iterator = iter(self.choices)
        if hasattr(iterator, '__next__'):
            empty_label = iterator.__next__()[1]
        else:
            empty_label = iterator.next()[1]  # Hacky way to getting the correct empty_label from the field instead of a hardcoded '--------'
        final_choices = []
        if value:
            available_choices = self._get_available_choices(self.queryset, value)
            for choice in available_choices:
                final_choices.append((choice.pk, force_text(choice)))
        final_choices = [("", (empty_label))] + final_choices
        if self.show_all:
            final_choices.append(("", (empty_label)))
            self.choices = list(self.choices)
            self.choices.sort(key=lambda x: unicode_sorter(x[1]))
            for ch in self.choices:
                if not ch in final_choices:
                    final_choices.append(ch)
        self.choices = ()
        final_attrs = self.build_attrs(attrs, name=name)
        if 'class' in final_attrs:
            final_attrs['class'] += ' chained'
        else:
            final_attrs['class'] = 'chained'
        final_attrs['data-ss-url'] = url
        final_attrs['data-ss-id'] = u'id_' + chain_field
        final_attrs['data-ss-value'] = value
        final_attrs['data-ss-auto_choose'] = auto_choose
        final_attrs['data-ss-empty_label'] = empty_label

        output = super(ChainedSelect, self).render(name, value, final_attrs, choices=final_choices)
        return mark_safe(output)

    def _get_available_choices(self, queryset, value):
        """
        get possible choices for selection
        """
        item = queryset.filter(pk=value).first()
        if item:
            try:
                pk = getattr(item, self.model_field + "_id")
                filter = {self.model_field: pk}
            except AttributeError:
                try:  # maybe m2m?
                    pks = getattr(item, self.model_field).all().values_list('pk', flat=True)
                    filter = {self.model_field + "__in": pks}
                except AttributeError:
                    try:  # maybe a set?
                        pks = getattr(item, self.model_field + "_set").all().values_list('pk', flat=True)
                        filter = {self.model_field + "__in": pks}
                    except:  # give up
                        filter = {}
            filtered = list(get_model(self.app_name, self.model_name).objects.filter(**filter).distinct())
            sort_results(filtered)
        else:
            # invalid value for queryset
            filtered = []

        return filtered
