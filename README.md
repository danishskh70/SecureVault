# SecureVault

A team-based secret management web application built with Django. Teams can securely store, share, and audit access to credentials and environment secrets — with role-based access control and a full audit trail.

## Features

- **Role-based access control** — Owner, Admin, Developer, Viewer roles with permission hierarchy
- **Team management** — Create teams, invite members via join keys, approve/reject requests
- **Secret management** — Encrypted storage of secrets scoped to projects
- **Audit log** — Every view, create, edit, and delete action is recorded
- **Superadmin panel** — Platform-wide oversight of all teams, projects, users, and secrets

## Tech Stack

- Python / Django
- SQLite (development)
- Django ORM
- HTML/CSS (custom, no framework)

## Setup
```bash
git clone https://github.com/danishskh70/SecureVault.git
cd SecureVault

python -m venv myenv
source myenv/bin/activate  # Windows: myenv\Scripts\activate

pip install -r requirements.txt

python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

## Roles

| Role | Can do |
|------|--------|
| Owner | Everything — team settings, members, projects, secrets |
| Admin | Manage members, approve requests, view audit log |
| Developer | Create, edit, delete secrets |
| Viewer | Read-only access to secrets |
| Superadmin | Platform-wide access to all teams and data |

## Project Structure
```
secretmanager/
├── core/               # Main app
│   ├── models.py       # Team, Project, Secret, Membership, AuditLog
│   ├── views.py        # All views including superadmin
│   ├── forms.py
│   ├── context_processors.py
│   └── templates/
└── secretmanager/      # Project settings
```