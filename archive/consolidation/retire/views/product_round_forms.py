"""Editable product facts for an app-owned round; no product records are changed."""
from uuid import uuid4
from django import forms
from django.forms import formset_factory
from django.utils.text import slugify

from apps.pipeline.services.round_product import lip_gloss_brief, classify_intake, DEFAULT_COPY_ROLES


class RoundForm(forms.Form):
    request_key = forms.UUIDField(widget=forms.HiddenInput)
    name = forms.CharField(label='Product name', max_length=120)
    product_type = forms.ChoiceField(label='Product type', choices=[('lip_gloss','Lip gloss'),('other','Another product')])
    shape = forms.ChoiceField(label='Container shape', required=False, choices=[('lip_gloss_wand','Square clear bottle with doe-foot wand'),('','Another form · use the panels below')])
    material = forms.CharField(label='Materials and closure', max_length=1500, widget=forms.Textarea(attrs={'rows':2}))
    width = forms.FloatField(label='Closed width (mm)', min_value=.1, max_value=2000)
    depth = forms.FloatField(label='Closed depth (mm)', min_value=.1, max_value=2000)
    height = forms.FloatField(label='Closed height (mm)', min_value=.1, max_value=2000)
    body_height = forms.FloatField(label='Body height (mm)', min_value=.1, max_value=2000, required=False)
    cap_height = forms.FloatField(label='Cap height (mm)', min_value=.1, max_value=2000, required=False)
    wall = forms.FloatField(label='Wall thickness (mm)', min_value=.1, max_value=100, required=False)
    carton_width = forms.FloatField(label='Carton internal width (mm)', min_value=.1, max_value=2000, required=False)
    carton_depth = forms.FloatField(label='Carton internal depth (mm)', min_value=.1, max_value=2000, required=False)
    carton_height = forms.FloatField(label='Carton internal height (mm)', min_value=.1, max_value=2000, required=False)
    provisional = forms.BooleanField(label='Measurements and shades are provisional', required=False,
                                     help_text='Provisional owner estimates can start a round.')
    brand = forms.CharField(label='Brand mark', max_length=100)
    collection = forms.CharField(label='Collection name instruction', max_length=300)
    leaflet = forms.CharField(label='Leaflet copy instruction', max_length=1500, widget=forms.Textarea(attrs={'rows':2}))
    product = forms.CharField(label='Product copy', max_length=300)
    net = forms.CharField(label='Net contents', max_length=150)
    back_en = forms.CharField(label='Carton back · English', widget=forms.Textarea(attrs={'rows':2}), max_length=1000)
    back_es = forms.CharField(label='Carton back · Español', widget=forms.Textarea(attrs={'rows':2}), max_length=1000)
    back_ar = forms.CharField(label='Carton back · العربية', widget=forms.Textarea(attrs={'rows':2,'dir':'auto'}), max_length=1000)
    inci = forms.CharField(label='INCI', max_length=500)
    batch = forms.CharField(label='Batch field', max_length=200)
    ean = forms.CharField(label='EAN frame', max_length=200)
    extra_copy = forms.CharField(label='Other required copy · one item per line', required=False,
                                 widget=forms.Textarea(attrs={'rows':3}), max_length=3000)
    truths = forms.CharField(label='Product truths · one per line', widget=forms.Textarea(attrs={'rows':4}), max_length=4000,
                             help_text='What it does, what it is made of, and the moments of using it. Every seed must link to one.')
    banned = forms.CharField(label='Banned motifs · one per line', widget=forms.Textarea(attrs={'rows':5}), max_length=4000)
    audience = forms.CharField(label='Audience', widget=forms.Textarea(attrs={'rows':2}), max_length=2000)
    bar = forms.CharField(label='Creative bar', widget=forms.Textarea(attrs={'rows':2}), max_length=2000)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for key, role in DEFAULT_COPY_ROLES.items():
            name = 'extra_copy' if key == 'required' else key
            self.fields[name + '_role'] = forms.ChoiceField(
                label=self.fields[name].label + ' · treatment', initial=role,
                choices=[('COPY', 'COPY · print these words verbatim'),
                         ('INSTRUCTION', 'INSTRUCTION · guide the design, never print')])
            self.fields[name].content_role = self.data.get(name + '_role', self.initial.get(name + '_role', role))
            self.fields[name].has_content_selector = True
        for field in self.fields.values():
            if not hasattr(field, 'content_role'):
                field.content_role = 'INSTRUCTION'
            if not isinstance(field.widget, (forms.HiddenInput, forms.CheckboxInput)):
                field.widget.attrs['class'] = 'field'

    def copy_entries(self):
        return [(self['extra_copy' if key == 'required' else key],
                 self[('extra_copy' if key == 'required' else key) + '_role']) for key in DEFAULT_COPY_ROLES]

    def clean(self):
        data=super().clean()
        carton=[data.get('carton_'+k) for k in ('width','depth','height')]
        if any(carton) and not all(carton):
            raise forms.ValidationError('Enter all three carton internal dimensions, or leave all three empty.')
        return data


class PanelForm(forms.Form):
    id = forms.SlugField(required=False, widget=forms.HiddenInput)
    label = forms.CharField(label='Panel', max_length=100)
    width_mm = forms.FloatField(label='Width mm', min_value=.1, max_value=2000, required=False)
    height_mm = forms.FloatField(label='Height mm', min_value=.1, max_value=2000, required=False)
    surface = forms.ChoiceField(label='Surface', initial='clear_acrylic', choices=[('clear_acrylic','Clear acrylic · liquid visible'),('gold_metal','Gold metal · marks only'),('carton','Carton'),('other','Other')])
    decoration = forms.CharField(label='Decoration and opacity', max_length=1000, required=False)
    blank_reason = forms.CharField(label='Intentionally blank panel · reason', max_length=1000, required=False,
                                   help_text='Leave empty unless this panel is deliberately blank before sketching.')
    engine_face = forms.ChoiceField(label='Carton face', required=False, choices=[('', 'Separate product panel'),('back','Carton back'),('side_left','Carton left'),('front','Carton front'),('side_right','Carton right'),('top_end','Carton top'),('bottom_end','Carton bottom')])

    def clean(self):
        data=super().clean()
        if not data.get('engine_face') and not (data.get('width_mm') and data.get('height_mm')):
            raise forms.ValidationError('Enter width and height for a product panel. Carton face sizes come from its internal dimensions.')
        return data


class ShadeForm(forms.Form):
    name = forms.CharField(label='Shade name', max_length=100)
    hex = forms.RegexField(label='Liquid colour hex', regex=r'^#[0-9a-fA-F]{6}$',
                          error_messages={'invalid':'Use a six-digit colour such as #C9707A.'},
                          widget=forms.TextInput(attrs={'placeholder':'#C9707A','pattern':'#[0-9a-fA-F]{6}','maxlength':7}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['name'].content_role = 'COPY'
        self.fields['hex'].content_role = 'INSTRUCTION'


PanelFormSet=formset_factory(PanelForm, extra=2, can_delete=True, max_num=40, validate_max=True)
ShadeFormSet=formset_factory(ShadeForm, extra=1, can_delete=True, max_num=20, validate_max=True)


def initial_values(brief):
    copy=brief.get('copy',{})
    dimensions=brief.get('dimensions_mm',{})
    initial={key:brief.get(key,'') for key in ('name','product_type','shape','material','audience','bar','provisional')}
    initial.update(dimensions)
    initial.update({key:copy.get(key,'') for key in ('brand','collection','product','net','back_en','back_es','back_ar','inci','batch','ean','leaflet')})
    initial['extra_copy']=copy.get('required','')
    initial['truths']='\n'.join(brief.get('truths',[]))
    initial['banned']='\n'.join(brief.get('banned',[]))
    initial['request_key']=uuid4()
    roles = brief.get('content_roles', {})
    for key, role in DEFAULT_COPY_ROLES.items():
        name = 'extra_copy' if key == 'required' else key
        initial[name + '_role'] = roles.get('copy.' + key, role)
    for key,value in zip(('width','depth','height'),brief.get('carton',{}).get('inside_mm',[])):
        initial['carton_'+key]=value
    return initial


def forms_for(data=None, *, generic=False):
    brief={'product_type':'other','shape':'','provisional':True} if generic else lip_gloss_brief()
    form=RoundForm(data,initial=initial_values(brief))
    panels=PanelFormSet(data,initial=brief.get('panels',[]),prefix='panels')
    shades=ShadeFormSet(data,initial=brief.get('shades',[]),prefix='shades')
    return form,panels,shades


def product_brief(form,panels,shades):
    """Called only after all three forms validate; normalize remains the final contract."""
    data=form.cleaned_data
    result={key:data[key] for key in ('name','product_type','shape','material','audience','bar','provisional')}
    result['dimensions_mm']={key:data[key] for key in ('width','depth','height','body_height','cap_height','wall') if data.get(key) is not None}
    result['carton']={'inside_mm':[data.get('carton_'+key) for key in ('width','depth','height')]} if data.get('carton_width') else {}
    result['copy']={key:data[key] for key in ('brand','collection','product','net','back_en','back_es','back_ar','inci','batch','ean','leaflet')}
    result['copy']['required']=data['extra_copy'].strip()
    for key in ('truths','banned'):
        result[key]=[line.strip() for line in data[key].splitlines() if line.strip()]
    result['shades']=[{'name':f.cleaned_data['name'],'hex':f.cleaned_data['hex'].upper()} for f in shades if f.cleaned_data and not f.cleaned_data.get('DELETE')]
    result['panels']=[]
    for f in panels:
        row=f.cleaned_data
        if not row or row.get('DELETE'): continue
        panel={key:row[key] for key in ('label','surface','decoration')}
        if row.get('blank_reason'):
            panel['blank_reason']=row['blank_reason']
        panel['id']=row.get('id') or row.get('engine_face') or slugify(row['label']).replace('-','_')
        if row.get('engine_face'): panel['engine_face']=row['engine_face']
        else: panel.update(width_mm=row['width_mm'],height_mm=row['height_mm'])
        result['panels'].append(panel)
    roles = {key: data[('extra_copy' if key == 'required' else key) + '_role'] for key in DEFAULT_COPY_ROLES}
    return classify_intake(result, roles)
