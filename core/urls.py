from django.urls import path
from . import views

urlpatterns = [
    # Auth
    path('signup/', views.signup, name='signup'),

    # Post-login landing
    path('', views.dashboard, name='dashboard'),

    # Superadmin team + project management
    path('superadmin/teams/create/', views.sa_create_team, name='sa_create_team'),
    path('superadmin/teams/<int:team_id>/delete/', views.sa_delete_team, name='sa_delete_team'),
    path('superadmin/teams/<int:team_id>/projects/', views.sa_project_list, name='sa_project_list'),
    path('superadmin/teams/<int:team_id>/projects/add/', views.sa_add_project, name='sa_add_project'),
    path('superadmin/teams/<int:team_id>/projects/<int:project_id>/delete/', views.sa_delete_project, name='sa_delete_project'),
    path('superadmin/teams/<int:team_id>/members/', views.sa_member_list, name='sa_member_list'),
    path('superadmin/teams/<int:team_id>/members/<int:membership_id>/role/', views.sa_change_role, name='sa_change_role'),
    path('superadmin/teams/<int:team_id>/members/<int:membership_id>/remove/', views.sa_remove_member, name='sa_remove_member'),
    path('superadmin/teams/<int:team_id>/requests/', views.sa_join_requests, name='sa_join_requests'),
    path('superadmin/teams/<int:team_id>/requests/<int:request_id>/approve/', views.sa_approve_request, name='sa_approve_request'),
    path('superadmin/teams/<int:team_id>/requests/<int:request_id>/reject/', views.sa_reject_request, name='sa_reject_request'),
    # Superadmin user management
    path('superadmin/users/', views.sa_user_list, name='sa_user_list'),
    path('superadmin/users/<int:user_id>/toggle-superadmin/', views.sa_toggle_superadmin, name='sa_toggle_superadmin'),
    path('superadmin/users/<int:user_id>/delete/', views.sa_delete_user, name='sa_delete_user'),
    path('superadmin/teams/<int:team_id>/projects/<int:project_id>/edit/', views.sa_edit_project, name='sa_edit_project'),

    # Team setup
    path('team/create/', views.create_team, name='create_team'),
    path('team/join/', views.join_team, name='join_team'),
    path('team/pending/', views.pending, name='pending'),

    # Team management (owner/admin only)
    path('team/settings/', views.team_settings, name='team_settings'),
    path('team/settings/transfer/', views.transfer_ownership, name='transfer_ownership'),
    path('team/members/', views.member_list, name='member_list'),
    path('team/members/<int:membership_id>/role/', views.change_role, name='change_role'),
    path('team/members/<int:membership_id>/remove/', views.remove_member, name='remove_member'),

    # Join requests
    path('team/requests/', views.join_requests, name='join_requests'),
    path('team/requests/<int:request_id>/approve/', views.approve_request, name='approve_request'),
    path('team/requests/<int:request_id>/reject/', views.reject_request, name='reject_request'),
    path('team/requests/<int:request_id>/cancel/', views.cancel_request, name='cancel_request'),

    # Projects
    path('projects/', views.project_list, name='project_list'),
    path('projects/add/', views.add_project, name='add_project'),
    path('projects/<int:project_id>/edit/', views.edit_project, name='edit_project'),
    path('projects/<int:project_id>/delete/', views.delete_project, name='delete_project'),

    # Secrets
    path('projects/<int:project_id>/secrets/', views.secret_list, name='secret_list'),
    path('projects/<int:project_id>/secrets/add/', views.add_secret, name='add_secret'),
    path('projects/<int:project_id>/secrets/<int:secret_id>/', views.secret_detail, name='secret_detail'),
    path('projects/<int:project_id>/secrets/<int:secret_id>/edit/', views.edit_secret, name='edit_secret'),
    path('projects/<int:project_id>/secrets/<int:secret_id>/delete/', views.delete_secret, name='delete_secret'),
    path('projects/<int:project_id>/secrets/<int:secret_id>/versions/', views.secret_versions, name='secret_versions'),
    path('projects/<int:project_id>/secrets/<int:secret_id>/versions/<int:version_id>/rollback/', views.rollback_secret, name='rollback_secret'),

    # Audit log
    path('audit/', views.audit_log, name='audit_log'),

    # Team switching
    path('team/switch/<int:team_id>/', views.switch_team, name='switch_team'),

    path('projects/<int:project_id>/secrets/import/', views.bulk_import, name='bulk_import'),

    # Superadmin
    path('superadmin/', views.superadmin_dashboard, name='superadmin_dashboard'),
]