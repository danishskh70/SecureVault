from django.db import models
from django.contrib.auth.models import User
from cryptography.fernet import Fernet
import secrets


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

    def __str__(self):
        return f"{self.user.username} ({self.role})"


class Team(models.Model):
    name = models.CharField(max_length=100)
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

    def set_value(self, raw_value):
        key = self.project.team.encryption_key.encode()
        f = Fernet(key)
        self.value = f.encrypt(raw_value.encode()).decode()

    def get_value(self):
        key = self.project.team.encryption_key.encode()
        f = Fernet(key)
        return f.decrypt(self.value.encode()).decode()

    def __str__(self):
        return f"{self.name} ({self.project.name})"


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