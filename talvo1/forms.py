from django import forms

from .models import UserProfile


class RegistrationOnboardingForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = [
            'target_role',
            'experience_level',
            'target_company',
            'interview_focus',
            'confidence_level',
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['target_role'].required = True
        self.fields['experience_level'].required = True
        self.fields['target_company'].required = True
        self.fields['interview_focus'].required = False
        self.fields['confidence_level'].required = False

        self.fields['target_role'].widget.attrs.update({
            'class': 'mt-2 w-full rounded-xl border border-gray-300 px-4 py-3 text-sm focus:border-indigo-500 focus:ring-indigo-500',
            'placeholder': 'e.g. Backend Engineer, Product Manager',
        })
        self.fields['experience_level'].widget.attrs.update({
            'class': 'mt-2 w-full rounded-xl border border-gray-300 px-4 py-3 text-sm focus:border-indigo-500 focus:ring-indigo-500',
        })
        self.fields['target_company'].widget.attrs.update({
            'class': 'mt-2 w-full rounded-xl border border-gray-300 px-4 py-3 text-sm focus:border-indigo-500 focus:ring-indigo-500',
            'placeholder': 'e.g. Google, Amazon, Microsoft',
        })
        self.fields['interview_focus'].widget.attrs.update({
            'class': 'mt-2 w-full rounded-xl border border-gray-300 px-4 py-3 text-sm focus:border-indigo-500 focus:ring-indigo-500',
            'placeholder': 'Behavioral, system design, leadership, etc.',
        })
        self.fields['confidence_level'].widget.attrs.update({
            'class': 'mt-2 w-full rounded-xl border border-gray-300 px-4 py-3 text-sm focus:border-indigo-500 focus:ring-indigo-500',
            'placeholder': '1 to 10',
            'min': '1',
            'max': '10',
        })

    confidence_level = forms.IntegerField(min_value=1, max_value=10, required=False)
