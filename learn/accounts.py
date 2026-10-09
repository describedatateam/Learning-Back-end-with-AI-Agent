"""Invite-only sign-up. Sign-in and sign-out use Django's own views (see config/urls.py)."""
from django import forms
from django.contrib.auth import login
from django.contrib.auth.forms import UserCreationForm
from django.db import transaction
from django.db.models import F
from django.shortcuts import redirect, render
from django.utils.translation import gettext_lazy as _

from .models import InviteCode


class SignUpForm(UserCreationForm):
    invite_code = forms.CharField(label=_('Invite code'), max_length=40)

    def clean_invite_code(self):
        code = self.cleaned_data['invite_code'].strip()
        invite = InviteCode.objects.filter(code__iexact=code).first()
        if invite is None or not invite.is_usable():
            raise forms.ValidationError(_('This invite code is not valid. Ask the person who invited you for a new one.'))
        self.invite = invite
        return code

    @transaction.atomic
    def save(self, commit=True):
        # Count the use only if a use is still left, so two people can't share the last one.
        claimed = InviteCode.objects.filter(pk=self.invite.pk, uses__lt=F('max_uses')).update(uses=F('uses') + 1)
        if not claimed:
            raise forms.ValidationError(_('This invite code has just been used up.'))
        return super().save(commit=commit)


def signup(request):
    if request.user.is_authenticated:
        return redirect('home')
    form = SignUpForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        try:
            user = form.save()
        except forms.ValidationError as exc:
            form.add_error('invite_code', exc)
        else:
            login(request, user)
            return redirect('home')
    return render(request, 'learn/signup.html', {'form': form})
