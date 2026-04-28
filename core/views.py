from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import Q
from django.contrib import messages
import io

from .models import (
    UserProfile, Team, Project, Secret,
    Membership, TeamJoinRequest, AuditLog,
    SecretVersion, ROLE_HIERARCHY, ROLE_CHOICES
)
from .forms import (
    SignupForm, CreateTeamForm, JoinTeamForm,
    ProjectForm, SecretForm, ApproveRequestForm,
    TeamForm, TransferOwnershipForm
)


# ─── Helpers ────────────────────────────────────────────────────────────────

def get_profile(user):
    return UserProfile.objects.filter(user=user).first()

def is_superadmin(user):
    p = get_profile(user)
    return p and p.role == 'superadmin'

def get_membership(user, team_id=None):
    if not team_id:
        profile = UserProfile.objects.filter(user=user).first()
        if profile and profile.active_team_id:
            team_id = profile.active_team_id
    if team_id:
        return Membership.objects.filter(user=user, team_id=team_id).select_related('team').first()
    return Membership.objects.filter(user=user).select_related('team').first()

def has_role(membership, required_role):
    """Return True if membership role >= required_role in hierarchy."""
    if not membership:
        return False
    return ROLE_HIERARCHY.get(membership.role, 0) >= ROLE_HIERARCHY.get(required_role, 0)

def get_accessible_projects(user):
    if is_superadmin(user):
        return Project.objects.all()
    membership = get_membership(user)
    if not membership:
        return Project.objects.none()
    return Project.objects.filter(team=membership.team)

def can_access(user, membership, role):
    if is_superadmin(user):
        return True
    return has_role(membership, role)

def get_pending_count(membership):
    """Return pending join request count for an owner/admin's team, else 0.
    Used to drive the nav badge — only counts status='pending'."""
    if not membership:
        return 0
    if membership.role not in ('owner', 'admin'):
        return 0
    return TeamJoinRequest.objects.filter(
        team=membership.team, status='pending'
    ).count()


# ─── Auth ────────────────────────────────────────────────────────────────────

def signup(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    if request.method == 'POST':
        form = SignupForm(request.POST)
        if form.is_valid():
            user = form.save()
            UserProfile.objects.create(user=user, role='user')
            login(request, user)
            return redirect('dashboard')
    else:
        form = SignupForm()
    return render(request, 'core/signup.html', {'form': form})


# ─── Dashboard ───────────────────────────────────────────────────────────────

@login_required
def dashboard(request):
    if is_superadmin(request.user):
        return redirect('superadmin_dashboard')
    membership = get_membership(request.user)
    if not membership:
        pending = TeamJoinRequest.objects.filter(
            user=request.user, status='pending'
        ).first()
        if pending:
            return redirect('pending')
        return redirect('create_team')
    return redirect('project_list')


# ─── Team Setup ──────────────────────────────────────────────────────────────

@login_required
def create_team(request):
    """Combined onboarding screen — handles both create-team and join-team POSTs."""
    if is_superadmin(request.user):
        return redirect('superadmin_dashboard')

    error = None

    if request.method == 'POST':
        # Distinguish which form was submitted by a hidden or named button
        if 'name' in request.POST and 'join_key' not in request.POST:
            # ── Create team form ──
            form = CreateTeamForm(request.POST)
            if form.is_valid():
                team = Team.objects.create(name=form.cleaned_data['name'])
                Membership.objects.create(user=request.user, team=team, role='owner')
                return redirect('project_list')
            # form invalid — fall through and re-render with form errors
            return render(request, 'core/create_team.html', {'form': form, 'error': error})

        elif 'join_key' in request.POST:
            # ── Join team form ──
            join_key = request.POST.get('join_key', '').strip()
            if not join_key:
                error = 'Please enter a join key.'
            else:
                try:
                    team = Team.objects.get(join_key=join_key)
                    already = TeamJoinRequest.objects.filter(
                        user=request.user, team=team
                    ).exists()
                    if already:
                        error = 'You already have a pending request for this team.'
                    else:
                        TeamJoinRequest.objects.create(user=request.user, team=team)
                        return redirect('pending')
                except Team.DoesNotExist:
                    error = 'Invalid join key. Please check and try again.'

    all_memberships = Membership.objects.filter(user=request.user)
    return render(request, 'core/create_team.html', {
        'form': CreateTeamForm(),
        'error': error,
        'has_teams': all_memberships.exists(),
    })


@login_required
def join_team(request):
    """Legacy URL kept so existing bookmarks/links don't 404.
    All join logic now lives in create_team. Redirect there."""
    if is_superadmin(request.user):
        return redirect('superadmin_dashboard')
    membership = get_membership(request.user)
    if membership:
        return redirect('project_list')
    return redirect('create_team')


@login_required
def pending(request):
    if is_superadmin(request.user):
        return redirect('superadmin_dashboard')
    membership = get_membership(request.user)
    if membership:
        return redirect('project_list')
    join_request = TeamJoinRequest.objects.filter(
        user=request.user
    ).select_related('team').order_by('-requested_at').first()
    return render(request, 'core/pending.html', {'join_request': join_request})


# ─── Team Management ─────────────────────────────────────────────────────────

@login_required
def team_settings(request):
    membership = get_membership(request.user)
    if not membership or not has_role(membership, 'owner'):
        return redirect('project_list')
    
    team = membership.team
    if request.method == 'POST':
        form = TeamForm(request.POST, instance=team)
        if form.is_valid():
            form.save()
            messages.success(request, f'Team "{team.name}" settings updated.')
            return redirect('team_settings')
    else:
        form = TeamForm(instance=team)
        
    return render(request, 'core/team_settings.html', {
        'team': team,
        'form': form,
        'membership': membership,
    })


@login_required
def transfer_ownership(request):
    membership = get_membership(request.user)
    if not membership or not has_role(membership, 'owner'):
        return redirect('project_list')
    
    team = membership.team
    # Get other members who can become owners
    other_memberships = Membership.objects.filter(team=team).exclude(user=request.user).select_related('user')
    other_users = [m.user for m in other_memberships]
    
    if request.method == 'POST':
        form = TransferOwnershipForm(request.POST, queryset=User.objects.filter(id__in=[u.id for u in other_users]))
        if form.is_valid():
            new_owner = form.cleaned_data['new_owner']
            # Change current owner to admin
            membership.role = 'admin'
            membership.save()
            
            # Change new owner role to owner
            new_membership = Membership.objects.get(team=team, user=new_owner)
            new_membership.role = 'owner'
            new_membership.save()
            
            messages.success(request, f'Ownership transferred to {new_owner.username}.')
            return redirect('project_list')
    else:
        form = TransferOwnershipForm(queryset=User.objects.filter(id__in=[u.id for u in other_users]))
        
    return render(request, 'core/transfer_ownership.html', {
        'team': team,
        'form': form,
        'membership': membership,
    })


@login_required
def member_list(request):
    membership = get_membership(request.user)

    # ✅ SUPERADMIN FLOW
    if is_superadmin(request.user):
        # superadmin must specify team (you don't have it here)
        return redirect('superadmin_dashboard')  # or handle differently

    # ❌ NO MEMBERSHIP
    if not membership:
        return redirect('create_team')

    # ❌ NOT ADMIN
    if not has_role(membership, 'admin'):
        return redirect('project_list')

    # ✅ SAFE TO USE membership.team
    team = membership.team

    members = Membership.objects.filter(
        team=team
    ).select_related('user').order_by('role')

    pending_requests = TeamJoinRequest.objects.filter(
        team=team, status='pending'
    ).count()

    return render(request, 'core/member_list.html', {
        'members': members,
        'team': team,
        'join_key': team.join_key,
        'pending_count': pending_requests,
        'my_membership': membership,
        'pending_request_count': pending_requests,
    })

@login_required
def change_role(request, membership_id):
    membership = get_membership(request.user)
    if not has_role(membership, 'admin') and not is_superadmin(request.user):
        return redirect('project_list')
    if is_superadmin(request.user):
        return redirect('superadmin_dashboard')
    target = get_object_or_404(Membership, id=membership_id, team=membership.team)
    if target.user == request.user:
        return redirect('member_list')
    if request.method == 'POST':
        new_role = request.POST.get('role')
        if new_role in dict(ROLE_CHOICES):
            target.role = new_role
            target.save()
        return redirect('member_list')
    return render(request, 'core/change_role.html', {
        'target': target,
        'role_choices': ROLE_CHOICES,
    })

@login_required
def remove_member(request, membership_id):
    membership = get_membership(request.user)
    if not has_role(membership, 'admin') and not is_superadmin(request.user):
        return redirect('project_list')
    if is_superadmin(request.user):
        return redirect('superadmin_dashboard')
    target = get_object_or_404(Membership, id=membership_id, team=membership.team)
    if target.user == request.user:
        return redirect('member_list')
    if request.method == 'POST':
        target.delete()
        return redirect('member_list')
    return render(request, 'core/confirm_remove.html', {
        'target': target,
    })


# ─── Join Requests ───────────────────────────────────────────────────────────

@login_required
def join_requests(request):
    membership = get_membership(request.user)
    if not has_role(membership, 'admin') and not is_superadmin(request.user):
        return redirect('project_list')
    if is_superadmin(request.user):
        return redirect('superadmin_dashboard')
    requests_qs = TeamJoinRequest.objects.filter(
        team=membership.team, status='pending'
    ).select_related('user', 'team')
    return render(request, 'core/join_requests.html', {
        'requests': requests_qs,
        'pending_request_count': requests_qs.count(),
    })

# ─── Projects ────────────────────────────────────────────────────────────────

@login_required
def project_list(request):
    projects = get_accessible_projects(request.user)
    membership = get_membership(request.user)
    return render(request, 'core/project_list.html', {
        'projects': projects,
        'team': membership.team if membership else None,
        'membership': membership,
        'is_superadmin': is_superadmin(request.user),
        
    })


@login_required
def add_project(request):
    membership = get_membership(request.user)
    if not can_access(request.user, membership, 'admin'):
        return redirect('project_list')
    if request.method == 'POST':
        form = ProjectForm(request.POST)
        if form.is_valid():
            team = membership.team if membership else None
            if is_superadmin(request.user):
                team_id = request.POST.get('team_id')
                team = get_object_or_404(Team, id=team_id)
            Project.objects.create(
                team=team,
                name=form.cleaned_data['name'],
                description=form.cleaned_data['description']
            )
            return redirect('project_list')
    else:
        form = ProjectForm()
    return render(request, 'core/add_project.html', {
        'form': form,
        'is_superadmin': is_superadmin(request.user),
        'teams': Team.objects.all() if is_superadmin(request.user) else None,
        
    })


@login_required
def edit_project(request, project_id):
    if is_superadmin(request.user):
        return redirect('superadmin_dashboard')
    membership = get_membership(request.user)
    if not membership or not has_role(membership, 'admin'):
        return redirect('project_list')
    project = get_object_or_404(Project, id=project_id, team=membership.team)
    if request.method == 'POST':
        form = ProjectForm(request.POST, instance=project)
        if form.is_valid():
            form.save()
            messages.success(request, f'Project "{project.name}" updated.')
            return redirect('project_list')
    else:
        form = ProjectForm(instance=project)
    return render(request, 'core/edit_project.html', {
        'form': form,
        'project': project,
        'membership': membership,
    })


@login_required
def delete_project(request, project_id):
    membership = get_membership(request.user)
    if is_superadmin(request.user):
        project = get_object_or_404(Project, id=project_id)
    else:
        if not has_role(membership, 'admin'):
            return redirect('project_list')
        project = get_object_or_404(Project, id=project_id, team=membership.team)
    if request.method == 'POST':
        team_id = project.team.id
        project.delete()
        if is_superadmin(request.user):
            return redirect('sa_project_list', team_id=team_id)
        return redirect('project_list')
    return render(request, 'core/confirm_delete_project.html', {
        'project': project,
        
    })


# ─── Secrets ─────────────────────────────────────────────────────────────────

@login_required
def secret_list(request, project_id):
    project = get_object_or_404(Project, id=project_id)
    membership = get_membership(request.user)
    if not is_superadmin(request.user):
        if not membership or project.team != membership.team:
            return redirect('project_list')
    secrets = Secret.objects.filter(project=project)
    return render(request, 'core/secret_list.html', {
        'project': project,
        'secrets': secrets,
        'membership': membership,
        'can_edit': can_access(request.user, membership, 'developer'),
        
    })


@login_required
def add_secret(request, project_id):
    if is_superadmin(request.user):
        project = get_object_or_404(Project, id=project_id)
        membership = None
    else:
        membership = get_membership(request.user)
        if not membership or not has_role(membership, 'developer'):
            return redirect('project_list')
        project = get_object_or_404(Project, id=project_id, team=membership.team)
    if request.method == 'POST':
        form = SecretForm(request.POST)
        if form.is_valid():
            secret = form.save(commit=False)
            secret.project = project
            secret.set_value(form.cleaned_data['value'])
            secret.save()
            AuditLog.objects.create(
                user=request.user,
                action='created',
                secret=secret,
                secret_name=secret.name
            )
            messages.success(request, f'Secret "{secret.name}" created.')
            return redirect('secret_list', project_id=project.id)
    else:
        form = SecretForm()
    return render(request, 'core/add_secret.html', {
        'form': form,
        'project': project,
        
    })


@login_required
def secret_detail(request, project_id, secret_id):
    if is_superadmin(request.user):
        project = get_object_or_404(Project, id=project_id)
        secret = get_object_or_404(Secret, id=secret_id, project=project)
        AuditLog.objects.create(
            user=request.user, action='viewed',
            secret=secret, secret_name=secret.name
        )
        return render(request, 'core/secret_detail.html', {
            'secret': secret,
            'project': project,
            'decrypted_value': secret.get_value(),
            'membership': None,
            'can_edit': True,
            'is_superadmin': True,
            # no pending_request_count — superadmin nav has no Requests link
        })

    membership = get_membership(request.user)
    if not membership:
        return redirect('dashboard')
    project = get_object_or_404(Project, id=project_id, team=membership.team)
    secret = get_object_or_404(Secret, id=secret_id, project=project)
    AuditLog.objects.create(
        user=request.user, action='viewed',
        secret=secret, secret_name=secret.name
    )
    return render(request, 'core/secret_detail.html', {
        'secret': secret,
        'project': project,
        'decrypted_value': secret.get_value(),
        'membership': membership,
        'can_edit': has_role(membership, 'developer'),
        'is_superadmin': False,
        
    })


@login_required
def edit_secret(request, project_id, secret_id):
    if is_superadmin(request.user):
        project = get_object_or_404(Project, id=project_id)
        membership = None
    else:
        membership = get_membership(request.user)
        if not membership or not has_role(membership, 'developer'):
            return redirect('project_list')
        project = get_object_or_404(Project, id=project_id, team=membership.team)
    secret = get_object_or_404(Secret, id=secret_id, project=project)
    if request.method == 'POST':
        form = SecretForm(request.POST, instance=secret)
        if form.is_valid():
            updated = form.save(commit=False)
            # save old value as version before overwriting
            last_version = updated.versions.count()
            SecretVersion.objects.create(
                secret=updated,
                encrypted_value=updated.value,
                changed_by=request.user,
                version_number=last_version + 1,
                action='edited'
            )
            updated.set_value(form.cleaned_data['value'])
            updated.save()
            AuditLog.objects.create(
                user=request.user, action='edited',
                secret=updated, secret_name=updated.name
            )
            messages.success(request, f'Secret "{updated.name}" updated.')
            return redirect('secret_list', project_id=project.id)
    else:
        form = SecretForm(instance=secret, initial={'value': secret.get_value()})
    return render(request, 'core/add_secret.html', {
        'form': form,
        'project': project,
        'editing': True,
        
    })


@login_required
def delete_secret(request, project_id, secret_id):
    if is_superadmin(request.user):
        project = get_object_or_404(Project, id=project_id)
        membership = None
    else:
        membership = get_membership(request.user)
        if not membership or not has_role(membership, 'developer'):
            return redirect('project_list')
        project = get_object_or_404(Project, id=project_id, team=membership.team)
    secret = get_object_or_404(Secret, id=secret_id, project=project)
    if request.method == 'POST':
        last_version = secret.versions.count()
        SecretVersion.objects.create(
            secret=secret,
            encrypted_value=secret.value,
            changed_by=request.user,
            version_number=last_version + 1,
            action='deleted'
        )
        AuditLog.objects.create(
            user=request.user, action='deleted',
            secret=secret, secret_name=secret.name
        )
        secret_name = secret.name
        secret.delete()
        messages.success(request, f'Secret "{secret_name}" deleted.')
        return redirect('secret_list', project_id=project.id)
    return render(request, 'core/confirm_delete.html', {
        'secret': secret,
        'project': project,
        
    })


# ─── Audit Log ───────────────────────────────────────────────────────────────

@login_required
def audit_log(request):
    membership = get_membership(request.user)
    if is_superadmin(request.user):
        logs = AuditLog.objects.select_related('user', 'secret').order_by('-timestamp')
        return render(request, 'core/audit_log.html', {
    'logs': logs,
    'is_superadmin': True,
    'membership': None,
    
})
    if not membership:
        return redirect('project_list')
    if membership.role in ['owner', 'admin']:
        projects = Project.objects.filter(team=membership.team)
        logs = AuditLog.objects.filter(
            secret__project__in=projects
        ).select_related('user', 'secret').order_by('-timestamp')
    else:
        logs = AuditLog.objects.filter(
            user=request.user
        ).select_related('user', 'secret').order_by('-timestamp')
    return render(request, 'core/audit_log.html', {
        'logs': logs,
        'is_superadmin': False,
        
    })


# ─── Superadmin ──────────────────────────────────────────────────────────────

@login_required
def superadmin_dashboard(request):
    if not is_superadmin(request.user):
        return redirect('project_list')
    return render(request, 'core/superadmin_dashboard.html', {
    'teams': Team.objects.all(),
    'projects': Project.objects.all(),
    'users': User.objects.all(),
    'secrets': Secret.objects.all(),
    'membership': None,
    
})


# ─── Superadmin Team + Project Management ────────────────────────────────────

@login_required
def sa_create_team(request):
    """Superadmin team creation — uses its own template, not the user onboarding screen."""
    if not is_superadmin(request.user):
        return redirect('project_list')
    if request.method == 'POST':
        form = CreateTeamForm(request.POST)
        if form.is_valid():
            Team.objects.create(name=form.cleaned_data['name'])
            return redirect('superadmin_dashboard')
    else:
        form = CreateTeamForm()
    return render(request, 'core/sa_create_team.html', {'membership': None,
'form': form})


@login_required
def sa_delete_team(request, team_id):
    if not is_superadmin(request.user):
        return redirect('project_list')
    team = get_object_or_404(Team, id=team_id)
    if request.method == 'POST':
        team.delete()
        return redirect('superadmin_dashboard')
    return render(request, 'core/sa_confirm_delete_team.html', {'membership': None,
'team': team})


@login_required
def sa_member_list(request, team_id):
    if not is_superadmin(request.user):
        return redirect('project_list')
    team = get_object_or_404(Team, id=team_id)
    members = Membership.objects.filter(team=team).select_related('user').order_by('role')
    pending_count = TeamJoinRequest.objects.filter(team=team, status='pending').count()
    return render(request, 'core/sa_member_list.html', {
    'team': team,
    'members': members,
    'pending_count': pending_count,
    'membership': None,
    
})


@login_required
def sa_change_role(request, team_id, membership_id):
    if not is_superadmin(request.user):
        return redirect('project_list')
    team = get_object_or_404(Team, id=team_id)
    target = get_object_or_404(Membership, id=membership_id, team=team)
    if request.method == 'POST':
        new_role = request.POST.get('role')
        if new_role in dict(ROLE_CHOICES):
            target.role = new_role
            target.save()
        return redirect('sa_member_list', team_id=team.id)
    return render(request, 'core/change_role.html', {'membership': None,

        'target': target,
        'role_choices': ROLE_CHOICES,
        'superadmin': True,
        'team': team,
    })


@login_required
def sa_edit_project(request, team_id, project_id):
    if not is_superadmin(request.user):
        return redirect('project_list')
    team = get_object_or_404(Team, id=team_id)
    project = get_object_or_404(Project, id=project_id, team=team)
    if request.method == 'POST':
        form = ProjectForm(request.POST, instance=project)
        if form.is_valid():
            form.save()
            return redirect('sa_project_list', team_id=team.id)
    else:
        form = ProjectForm(instance=project)
    return render(request, 'core/sa_add_project.html', {'membership': None,
        'form': form,
        'team': team,
        'project': project,
        'editing': True,
        'superadmin': True,
    })


@login_required
def sa_remove_member(request, team_id, membership_id):
    if not is_superadmin(request.user):
        return redirect('project_list')
    team = get_object_or_404(Team, id=team_id)
    target = get_object_or_404(Membership, id=membership_id, team=team)
    if request.method == 'POST':
        target.delete()
        return redirect('sa_member_list', team_id=team.id)
    return render(request, 'core/confirm_remove.html', {'membership': None,

        'target': target,
        'superadmin': True,
        'team': team,
    })


@login_required
def sa_join_requests(request, team_id):
    if not is_superadmin(request.user):
        return redirect('project_list')
    team = get_object_or_404(Team, id=team_id)
    requests_qs = TeamJoinRequest.objects.filter(
        team=team, status='pending'
    ).select_related('user', 'team')
    return render(request, 'core/join_requests.html', {'membership': None,
    'requests': requests_qs,
    'superadmin': True,
    'team': team,
})


@login_required
def sa_approve_request(request, team_id, request_id):
    if not is_superadmin(request.user):
        return redirect('project_list')
    team = get_object_or_404(Team, id=team_id)
    join_request = get_object_or_404(
        TeamJoinRequest, id=request_id, team=team, status='pending'
    )

    if request.method == 'POST':
        # Assign default role (e.g., 'viewer') for superadmin approval
        Membership.objects.create(
            user=join_request.user,
            team=join_request.team,
            role='viewer'
        )
        join_request.status = 'approved'
        join_request.save()
        return redirect('sa_join_requests', team_id=team.id)

    return render(request, 'core/approve_request.html', {
        # 'membership': None,
        'join_request': join_request,
        'superadmin': True,
        'team': team,
    })

@login_required
def sa_reject_request(request, team_id, request_id):
    if not is_superadmin(request.user):
        return redirect('project_list')
    team = get_object_or_404(Team, id=team_id)
    join_request = get_object_or_404(
        TeamJoinRequest, id=request_id, team=team, status='pending'
    )
    if request.method == 'POST':
        join_request.status = 'rejected'
        join_request.save()
        return redirect('sa_join_requests', team_id=team.id)
    return render(request, 'core/confirm_reject.html', {'membership': None,

        'join_request': join_request,
        'superadmin': True,
        'team': team,
    })


@login_required
def sa_delete_project(request, team_id, project_id):
    if not is_superadmin(request.user):
        return redirect('project_list')
    team = get_object_or_404(Team, id=team_id)
    project = get_object_or_404(Project, id=project_id, team=team)
    if request.method == 'POST':
        project.delete()
        return redirect('sa_project_list', team_id=team.id)
    return render(request, 'core/confirm_delete_project.html', {'membership': None,
        'project': project,
        'superadmin': True,
        'team': team,
    })


@login_required
def sa_project_list(request, team_id):
    if not is_superadmin(request.user):
        return redirect('project_list')
    team = get_object_or_404(Team, id=team_id)
    projects = Project.objects.filter(team=team)
    return render(request, 'core/sa_project_list.html', {
    'team': team,
    'projects': projects,
    'membership': None,
    
})


@login_required
def sa_add_project(request, team_id):
    if not is_superadmin(request.user):
        return redirect('project_list')
    team = get_object_or_404(Team, id=team_id)
    if request.method == 'POST':
        form = ProjectForm(request.POST)
        if form.is_valid():
            Project.objects.create(
                team=team,
                name=form.cleaned_data['name'],
                description=form.cleaned_data['description']
            )
            return redirect('sa_project_list', team_id=team.id)
    else:
        form = ProjectForm()
    return render(request, 'core/sa_add_project.html', {'membership': None,

        'form': form,
        'team': team,
        'superadmin': True,
    })


# ─── Superadmin User Management ──────────────────────────────────────────────

@login_required
def sa_user_list(request):
    if not is_superadmin(request.user):
        return redirect('project_list')
    users = User.objects.all().select_related('userprofile').prefetch_related('membership_set__team')
    return render(request, 'core/sa_user_list.html', {
        'users': users,
        'membership': None,
    })

@login_required
def sa_toggle_superadmin(request, user_id):
    if not is_superadmin(request.user):
        return redirect('project_list')
    if request.user.id == user_id:
        return redirect('sa_user_list')
    target_user = get_object_or_404(User, id=user_id)
    profile, _ = UserProfile.objects.get_or_create(
        user=target_user, defaults={'role': 'user'}
    )
    if request.method == 'POST':
        profile.role = 'user' if profile.role == 'superadmin' else 'superadmin'
        profile.save()
        return redirect('sa_user_list')
    return render(request, 'core/sa_confirm_toggle_superadmin.html', {'membership': None,

        'target_user': target_user,
        'profile': profile,
    })


@login_required
def sa_delete_user(request, user_id):
    if not is_superadmin(request.user):
        return redirect('project_list')
    if request.user.id == user_id:
        return redirect('sa_user_list')
    target_user = get_object_or_404(User, id=user_id)
    if request.method == 'POST':
        target_user.delete()
        return redirect('sa_user_list')
    memberships = Membership.objects.filter(user=target_user).select_related('team')
    return render(request, 'core/sa_confirm_delete_user.html', {'membership': None,

        'target_user': target_user,
        'memberships': memberships,
    })

@login_required
def switch_team(request, team_id):
    membership = get_object_or_404(Membership, user=request.user, team_id=team_id)
    profile, _ = UserProfile.objects.get_or_create(user=request.user, defaults={'role': 'user'})
    profile.active_team_id = membership.team.pk
    profile.save()
    messages.success(request, f"Switched to team: {membership.team.name}")
    return redirect('project_list')


def parse_import_file(file):
    name = file.name.lower()
    content = file.read().decode('utf-8', errors='ignore')
    pairs = []

    if name.endswith('.env'):
        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if '=' in line:
                key, _, val = line.partition('=')
                pairs.append((key.strip(), val.strip()))

    elif name.endswith('.csv'):
        for line in content.splitlines():
            parts = line.split(',', 1)
            if len(parts) == 2:
                key, val = parts
                if key.strip() and key.strip().upper() != 'KEY':
                    pairs.append((key.strip(), val.strip()))

    elif name.endswith('.json'):
        import json
        try:
            data = json.loads(content)
            if isinstance(data, dict):
                pairs = [(k, str(v)) for k, v in data.items()]
        except json.JSONDecodeError:
            pass

    return pairs


@login_required
def bulk_import(request, project_id):
    if is_superadmin(request.user):
        project = get_object_or_404(Project, id=project_id)
        membership = None
    else:
        membership = get_membership(request.user)
        if not membership or not has_role(membership, 'developer'):
            return redirect('project_list')
        project = get_object_or_404(Project, id=project_id, team=membership.team)

    if request.method == 'POST':
        # CONFIRM stage — actually save
        if 'confirm' in request.POST:
            keys   = request.POST.getlist('keys')
            values = request.POST.getlist('values')
            skips  = request.POST.getlist('skip')

            for key, val in zip(keys, values):
                if key in skips:
                    continue
                existing = Secret.objects.filter(name=key, project=project).first()
                if existing:
                    # overwrite — save version first
                    last_version = existing.versions.count()
                    SecretVersion.objects.create(
                        secret=existing,
                        encrypted_value=existing.value,
                        changed_by=request.user,
                        version_number=last_version + 1,
                        action='edited'
                    )
                    existing.set_value(val)
                    existing.save()
                    AuditLog.objects.create(
                        user=request.user, action='edited',
                        secret=existing, secret_name=existing.name
                    )
                else:
                    s = Secret(name=key, project=project)
                    s.set_value(val)
                    s.save()
                    SecretVersion.objects.create(
                        secret=s,
                        encrypted_value=s.value,
                        changed_by=request.user,
                        version_number=1,
                        action='imported'
                    )
                    AuditLog.objects.create(
                        user=request.user, action='created',
                        secret=s, secret_name=s.name
                    )
            messages.success(request, 'Secrets imported successfully.')
            return redirect('secret_list', project_id=project.id)

        # PREVIEW stage — parse file
        file = request.FILES.get('import_file')
        if not file:
            return render(request, 'core/bulk_import.html', {
                'project': project,
                'error': 'No file selected.',
                'membership': membership,
            })

        ext = file.name.lower().split('.')[-1]
        if ext not in ('env', 'csv', 'json'):
            return render(request, 'core/bulk_import.html', {
                'project': project,
                'error': 'Unsupported file type. Use .env, .csv, or .json',
                'membership': membership,
            })

        pairs = parse_import_file(file)
        if not pairs:
            return render(request, 'core/bulk_import.html', {
                'project': project,
                'error': 'No valid key=value pairs found in file.',
                'membership': membership,
            })

        # mark duplicates
        preview = []
        for key, val in pairs:
            exists = Secret.objects.filter(name=key, project=project).exists()
            preview.append({'key': key, 'val': val, 'exists': exists})

        return render(request, 'core/bulk_import.html', {
            'project': project,
            'preview': preview,
            'membership': membership,
        })

    return render(request, 'core/bulk_import.html', {
        'project': project,
        'membership': membership,
    })


@login_required
def secret_versions(request, project_id, secret_id):
    if is_superadmin(request.user):
        project = get_object_or_404(Project, id=project_id)
        membership = None
    else:
        membership = get_membership(request.user)
        if not membership:
            return redirect('project_list')
        project = get_object_or_404(Project, id=project_id, team=membership.team)
    secret = get_object_or_404(Secret, id=secret_id, project=project)
    versions = secret.versions.all().order_by('-version_number')
    return render(request, 'core/secret_versions.html', {
        'secret': secret,
        'project': project,
        'versions': versions,
        'membership': membership,
        'can_edit': can_access(request.user, membership, 'developer'),
    })


@login_required
def rollback_secret(request, project_id, secret_id, version_id):
    if is_superadmin(request.user):
        project = get_object_or_404(Project, id=project_id)
        membership = None
    else:
        membership = get_membership(request.user)
        if not membership or not has_role(membership, 'developer'):
            return redirect('project_list')
        project = get_object_or_404(Project, id=project_id, team=membership.team)
    secret = get_object_or_404(Secret, id=secret_id, project=project)
    version = get_object_or_404(SecretVersion, id=version_id, secret=secret)

    if request.method == 'POST':
        # save current as version first
        last_version = secret.versions.count()
        SecretVersion.objects.create(
            secret=secret,
            encrypted_value=secret.value,
            changed_by=request.user,
            version_number=last_version + 1,
            action='edited'
        )
        # restore old version value directly — already encrypted
        secret.value = version.encrypted_value
        secret.save()
        AuditLog.objects.create(
            user=request.user, action='edited',
            secret=secret, secret_name=secret.name
        )
        messages.success(request, f'Restored v{version.version_number} of "{secret.name}".')
        return redirect('secret_versions', project_id=project.id, secret_id=secret.id)

    return render(request, 'core/confirm_rollback.html', {
        'secret': secret,
        'project': project,
        'version': version,
        'membership': membership,
    })


@login_required
def cancel_request(request, request_id):
    join_request = get_object_or_404(TeamJoinRequest, id=request_id, user=request.user, status='pending')
    if request.method == 'POST':
        join_request.delete()
        messages.success(request, 'Join request cancelled.')
        return redirect('create_team')
    return redirect('pending')


# ─── Approvals ───

@login_required
def approve_request(request, request_id):
    membership = get_membership(request.user)
    if not has_role(membership, 'admin') and not is_superadmin(request.user):
        return redirect('project_list')
    if is_superadmin(request.user):
        return redirect('superadmin_dashboard')
    join_request = get_object_or_404(
        TeamJoinRequest, id=request_id, team=membership.team, status='pending'
    )
    if request.method == 'POST':
        form = ApproveRequestForm(request.POST)
        if form.is_valid():
            Membership.objects.create(
                user=join_request.user,
                team=join_request.team,
                role=form.cleaned_data['role']
            )
            join_request.status = 'approved'
            join_request.save()
            messages.success(request, f'{join_request.user.username} approved.')
            return redirect('join_requests')
    else:
        form = ApproveRequestForm()
    return render(request, 'core/approve_request.html', {
        'join_request': join_request,
        'form': form,
    })


@login_required
def reject_request(request, request_id):
    membership = get_membership(request.user)
    if not has_role(membership, 'admin') and not is_superadmin(request.user):
        return redirect('project_list')
    if is_superadmin(request.user):
        return redirect('superadmin_dashboard')
    join_request = get_object_or_404(
        TeamJoinRequest, id=request_id, team=membership.team, status='pending'
    )
    if request.method == 'POST':
        join_request.status = 'rejected'
        join_request.save()
        messages.success(request, f'Request rejected.')
        return redirect('join_requests')
    return render(request, 'core/confirm_reject.html', {
        'join_request': join_request,
    })