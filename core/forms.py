from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.models import User
from .models import Secret, ROLE_CHOICES, Project, Team


class SignupForm(UserCreationForm):
    class Meta:
        model = User
        fields = ['username', 'password1', 'password2']


class LoginForm(AuthenticationForm):
    pass


class CreateTeamForm(forms.Form):
    name = forms.CharField(max_length=100, label='Team Name')


class TeamForm(forms.ModelForm):
    class Meta:
        model = Team
        fields = ['name', 'description']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
        }


class TransferOwnershipForm(forms.Form):
    new_owner = forms.ModelChoiceField(
        queryset=User.objects.none(),
        label='Select New Owner'
    )

    def __init__(self, *args, **kwargs):
        queryset = kwargs.pop('queryset', User.objects.none())
        super().__init__(*args, **kwargs)
        self.fields['new_owner'].queryset = queryset


class JoinTeamForm(forms.Form):
    join_key = forms.CharField(max_length=20, label='Team Join Key')


class ProjectForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = ['name', 'description']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
        }
        labels = {
            'name': 'Project Name',
        }


class SecretForm(forms.ModelForm):
    value = forms.CharField(
        widget=forms.PasswordInput(render_value=True),
        label='Secret Value'
    )

    class Meta:
        model = Secret
        fields = ['name', 'value']


class ApproveRequestForm(forms.Form):
    role = forms.ChoiceField(
        choices=ROLE_CHOICES,
        initial='developer',
        label='Assign Role'
    )