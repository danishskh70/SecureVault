from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.models import User
from .models import Secret, ROLE_CHOICES


class SignupForm(UserCreationForm):
    class Meta:
        model = User
        fields = ['username', 'password1', 'password2']


class LoginForm(AuthenticationForm):
    pass


class CreateTeamForm(forms.Form):
    name = forms.CharField(max_length=100, label='Team Name')


class JoinTeamForm(forms.Form):
    join_key = forms.CharField(max_length=20, label='Team Join Key')


class ProjectForm(forms.Form):
    name = forms.CharField(max_length=100, label='Project Name')
    description = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 3}),
        required=False,
        label='Description'
    )


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