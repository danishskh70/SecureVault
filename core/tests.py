from django.test import TestCase
from django.contrib.auth.models import User
from core.models import Team, Membership

class HierarchyTest(TestCase):
    def setUp(self):
        # Create a test team and user
        self.team = Team.objects.create(name="TestTeam")
        self.user = User.objects.create(username="testuser")
        Membership.objects.create(user=self.user, team=self.team, role='developer')

    def test_membership_exists(self):
        self.assertEqual(self.team.membership_set.count(), 1)
        self.assertEqual(self.user.membership_set.first().team.name, "TestTeam")