"""Product and display facts for an ideas-only round; no production intake."""
from uuid import uuid4

from django import forms
from django.forms import formset_factory

from apps.pipeline.services.round_designer import SCHEMA, gloss_brief, normalize_ideas_brief


def stand_type_choices():
    from apps.dielines.geometry.stand_types import buildable
    return [(row['id'], row['label']) for row in buildable()]


def suggested_type(data):
    """The engine's suggestion for what the form holds: its count, rows and the product's height."""
    from apps.dielines.geometry.stand_types import suggest
    return suggest(count=data.get('stand_count') or 12, rows=data.get('stand_rows'), product_height_mm=data.get('height'))['type']


class IdeasRoundForm(forms.Form):
    request_key = forms.UUIDField(widget=forms.HiddenInput)
    name = forms.CharField(label='Product name', max_length=120)
    product_type = forms.CharField(label='Product type', max_length=120)
    shape = forms.CharField(label='Product shape', max_length=500, required=False)
    material = forms.CharField(label='Materials and closure', max_length=1500,
                               widget=forms.Textarea(attrs={'rows': 2}))
    width = forms.FloatField(label='Product width (mm)', min_value=.1, max_value=2000, required=False)
    depth = forms.FloatField(label='Product depth (mm)', min_value=.1, max_value=2000, required=False)
    height = forms.FloatField(label='Product height (mm)', min_value=.1, max_value=2000, required=False)
    cap_height = forms.FloatField(label='Cap height (mm), if known', min_value=.1, max_value=2000, required=False)
    diameter = forms.FloatField(label='Diameter (mm), if relevant', min_value=.1, max_value=2000, required=False)
    measurements_provisional = forms.BooleanField(label='Measurements are provisional', required=False)
    stand_count = forms.IntegerField(label='Products held by the stand', min_value=1, max_value=100)
    stand_material = forms.CharField(label='Stand material', max_length=1000)
    stand_width = forms.FloatField(label='Stand width (mm)', min_value=.1, max_value=5000, required=False)
    stand_depth = forms.FloatField(label='Stand depth (mm)', min_value=.1, max_value=5000, required=False)
    stand_height = forms.FloatField(label='Stand height (mm)', min_value=.1, max_value=5000, required=False)
    stand_board_thickness = forms.FloatField(label='Board thickness (mm)', min_value=.1, max_value=100, required=False)
    stand_columns = forms.IntegerField(label='Columns, if known', min_value=1, max_value=100, required=False)
    stand_rows = forms.IntegerField(label='Rows, if known', min_value=1, max_value=100, required=False)
    stand_provisional = forms.BooleanField(label='Stand measurements are provisional', required=False)
    stand_type = forms.ChoiceField(label='Stand type', required=False, choices=[('', 'The engine\u2019s suggestion')] + stand_type_choices(), widget=forms.HiddenInput)
    brand = forms.CharField(label='Brand name', max_length=100)
    product = forms.CharField(label='Product words · English and Arabic', max_length=300,
                              widget=forms.TextInput(attrs={'dir': 'auto'}))
    truths = forms.CharField(label='Product truths · one per line', max_length=4000,
                             widget=forms.Textarea(attrs={'rows': 4}))
    banned = forms.CharField(label='Motifs to avoid · one per line', max_length=4000, required=False,
                             widget=forms.Textarea(attrs={'rows': 4}))
    audience = forms.CharField(label='Audience', max_length=2000, widget=forms.Textarea(attrs={'rows': 2}))
    bar = forms.CharField(label='Creative ambition', max_length=2000, widget=forms.Textarea(attrs={'rows': 2}))

    def sections(self):
        return [
            ('The product', [self[key] for key in ('name', 'product_type', 'shape', 'material')]),
            ('Product measurements · optional', [self[key] for key in ('width', 'depth', 'height', 'cap_height', 'diameter', 'measurements_provisional')]),
            ('The stand', [self[key] for key in ('stand_count', 'stand_material', 'stand_width', 'stand_depth', 'stand_height', 'stand_board_thickness', 'stand_columns', 'stand_rows', 'stand_provisional')]),
            ('Words on the design', [self[key] for key in ('brand', 'product')]),
            ('Where the ideas come from', [self[key] for key in ('truths', 'banned', 'audience', 'bar')]),
        ]


class ShadeForm(forms.Form):
    name = forms.CharField(label='Shade name', max_length=100)
    hex = forms.RegexField(label='Colour hex', regex=r'^#[0-9a-fA-F]{6}$',
        error_messages={'invalid': 'Use a six-digit colour such as #C9707A.'},
        widget=forms.TextInput(attrs={'placeholder': '#C9707A', 'pattern': '#[0-9a-fA-F]{6}', 'maxlength': 7}))
    name_arabic = forms.RegexField(label='Shade name in Arabic', max_length=100, required=False,
        regex=r'^[^A-Za-z]*[\u0600-\u06ff][^A-Za-z]*$',
        error_messages={'invalid': 'Use Arabic letters only, such as إمبر جلو.'},
        widget=forms.TextInput(attrs={'dir': 'rtl', 'lang': 'ar'}))


ShadeFormSet = formset_factory(ShadeForm, extra=1, can_delete=True, max_num=20, validate_max=True)


def initial_values(brief):
    initial = {key: brief.get(key, '') for key in ('name', 'product_type', 'shape', 'material', 'audience', 'bar')}
    initial.update(brief.get('dimensions_mm', {}))
    initial['measurements_provisional'] = brief.get('measurements_provisional', True)
    initial.update({key: brief.get('copy', {}).get(key, '') for key in ('brand', 'product')})
    initial.update({key: '\n'.join(brief.get(key, [])) for key in ('truths', 'banned')})
    stand = brief.get('stand', {})
    initial.update(stand_count=stand.get('count', 12), stand_material=stand.get('material', 'rigid paperboard'),
                   stand_provisional=stand.get('provisional', True))
    initial.update({'stand_' + key: value for key, value in stand.get('dimensions_mm', {}).items()})
    initial.update({'stand_' + key: value for key, value in stand.get('layout', {}).items()})
    initial['request_key'] = uuid4()
    return initial


def forms_for(data=None, *, generic=False, words=''):
    brief = ({'copy': {'brand': 'BBROSE'}, 'stand': {'count': 12, 'material': 'rigid paperboard'},
              'measurements_provisional': True, 'bar': words[:2000]} if generic or words else gloss_brief())
    return (IdeasRoundForm(data, initial=initial_values(brief)),
            ShadeFormSet(data, initial=brief.get('shades', []), prefix='shades'))


def product_brief(form, shades, *, flow=None):
    """Only declared intake fields enter the ideas contract, regardless of POST extras."""
    data = form.cleaned_data
    result = {key: data[key] for key in ('name', 'product_type', 'shape', 'material', 'audience', 'bar', 'measurements_provisional')}
    result['schema'] = SCHEMA
    if flow is not None:
        result['flow'] = flow
    result['dimensions_mm'] = {key: data[key] for key in ('width', 'depth', 'height', 'cap_height', 'diameter') if data.get(key) is not None}
    result['copy'] = {key: data[key] for key in ('brand', 'product')}
    result['stand'] = {'count': data['stand_count'], 'material': data['stand_material'],
        'provisional': data['stand_provisional'], 'type': data.get('stand_type') or suggested_type(data),
        'dimensions_mm': {key: data['stand_' + key] for key in ('width', 'depth', 'height', 'board_thickness')
                          if data.get('stand_' + key) is not None},
        'layout': {key: data['stand_' + key] for key in ('columns', 'rows') if data.get('stand_' + key) is not None}}
    for key in ('truths', 'banned'):
        result[key] = [line.strip() for line in data[key].splitlines() if line.strip()]
    result['shades'] = [dict({'name': row.cleaned_data['name'], 'hex': row.cleaned_data['hex'].upper()},
                             **({'name_arabic': row.cleaned_data['name_arabic'].strip()}
                                if row.cleaned_data.get('name_arabic', '').strip() else {}))
        for row in shades if row.cleaned_data and not row.cleaned_data.get('DELETE')]
    return normalize_ideas_brief(result)
