from django import forms

from .models import EvidenceLink


class EvidenceLinkForm(forms.ModelForm):
    class Meta:
        model = EvidenceLink
        fields = ["label", "document_type", "url", "version", "comment"]
        widgets = {"comment": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")
