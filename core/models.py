from django.db import models
from django.contrib.auth.models import User
from django.conf import settings
from cryptography.fernet import Fernet
import secrets
import hashlib
import base64


# --- Helpers ---

def generate_join_key():
    return 'team-' + secrets.token_hex(4)  # e.g. team-a3f9c1b2

def generate_encryption_key():
    return Fernet.generate_key().decode()


# --- Role hierarchy ---

ROLE_HIERARCHY = {
    'owner':     4,
    'admin':     3,
    'developer': 2,
    'viewer':    1,
}

ROLE_CHOICES = [
    ('owner',     'Owner'),
    ('admin',     'Admin'),
    ('developer', 'Developer'),
    ('viewer',    'Viewer'),
]


# --- Models ---

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    role = models.CharField(max_length=20, default='user')  # superadmin / user
    active_team = models.ForeignKey('Team', null=True, blank=True, on_delete=models.SET_NULL)

    def __str__(self):
        return f"{self.user.username} ({self.role})"


class Team(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, default='')
    encryption_key = models.TextField(default=generate_encryption_key)
    join_key = models.CharField(max_length=20, unique=True, default=generate_join_key)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Project(models.Model):
    team = models.ForeignKey(Team, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.team.name})"


class Secret(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    value = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def _get_fernet(self):
        master = settings.VAULT_MASTER_KEY.encode()
        team_key = self.project.team.encryption_key.encode()
        # Derive a key from master + team_key
        derived = hashlib.sha256(master + team_key).digest()
        return Fernet(base64.urlsafe_b64encode(derived))

    def set_value(self, raw_value):
        f = self._get_fernet()
        self.value = f.encrypt(raw_value.encode()).decode()

    def get_value(self):
        f = self._get_fernet()
        return f.decrypt(self.value.encode()).decode()

    def __str__(self):
        return f"{self.name} ({self.project.name})"


class SecretVersion(models.Model):
    secret = models.ForeignKey(Secret, on_delete=models.SET_NULL, null=True, blank=True, related_name='versions')
    encrypted_value = models.TextField()
    changed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    changed_at = models.DateTimeField(auto_now_add=True)
    version_number = models.PositiveIntegerField(default=1)
    action = models.CharField(max_length=20, default='edited')  # edited, deleted, imported

    class Meta:
        ordering = ['-version_number']

    def get_value(self):
        return self.secret._get_fernet().decrypt(self.encrypted_value.encode()).decode()


class Membership(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    team = models.ForeignKey(Team, on_delete=models.CASCADE)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='viewer')
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'team')

    def __str__(self):
        return f"{self.user.username} → {self.team.name} ({self.role})"


class TeamJoinRequest(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    team = models.ForeignKey(Team, on_delete=models.CASCADE)
    status = models.CharField(max_length=20, default='pending')  # pending / approved / rejected
    requested_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'team')

    def __str__(self):
        return f"{self.user.username} → {self.team.name} ({self.status})"


class AuditLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    action = models.CharField(max_length=50)
    secret = models.ForeignKey(Secret, on_delete=models.SET_NULL, null=True, blank=True)
    secret_name = models.CharField(max_length=100, default='')
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} {self.action} '{self.secret_name}'"