from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from core.models import Team, Membership, Project, Secret, SecretVersion

class HierarchyTest(TestCase):
    def setUp(self):
        # Create a test team and user
        self.team = Team.objects.create(name="TestTeam")
        self.user = User.objects.create(username="testuser")
        Membership.objects.create(user=self.user, team=self.team, role='developer')

    def test_membership_exists(self):
        self.assertEqual(self.team.membership_set.count(), 1)
        self.assertEqual(self.user.membership_set.first().team.name, "TestTeam")

class EditSecretBugTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="password")
        self.team = Team.objects.create(name="Test Team")
        self.membership = Membership.objects.create(user=self.user, team=self.team, role='developer')
        self.project = Project.objects.create(name="Test Project", team=self.team)
        
        # Create a secret
        self.secret = Secret.objects.create(name="Test Secret", project=self.project)
        self.secret.set_value("initial_secret_value")
        self.secret.save()
        
        self.client = Client()
        self.client.login(username="testuser", password="password")

    def test_edit_secret_version_encryption(self):
        # We edit the secret. The version created should contain the OLD encrypted value,
        # not the NEW plaintext value.
        new_value = "new_secret_value"
        url = reverse('edit_secret', kwargs={'project_id': self.project.id, 'secret_id': self.secret.id})
        
        response = self.client.post(url, {
            'name': 'Test Secret',
            'value': new_value
        })
        
        self.assertEqual(response.status_code, 302) # Redirect on success
        
        # Check the latest version
        version = SecretVersion.objects.filter(secret=self.secret).first()
        self.assertIsNotNone(version)
        
        # In a buggy state, version.encrypted_value == new_value
        self.assertNotEqual(version.encrypted_value, new_value, "Version saved the NEW plaintext value instead of the OLD encrypted value!")
        
        # Also check if it's the old encrypted value.
        try:
            decrypted = self.secret._get_fernet().decrypt(version.encrypted_value.encode()).decode()
            self.assertEqual(decrypted, "initial_secret_value")
        except Exception as e:
            self.fail(f"Could not decrypt version value: {e}. It might be plaintext: {version.encrypted_value}")
