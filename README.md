README needs updating — session added a lot. Rewrite:

```markdown
# SecureVault

A team-based secret management web application built with Django. Teams can securely store, share, and audit access to credentials and environment secrets — with role-based access control, envelope encryption, and a full audit trail.

## Features

- **Role-based access control** — Owner, Admin, Developer, Viewer roles with permission hierarchy
- **Multi-team support** — Users can belong to multiple teams, switch active team from nav
- **Envelope encryption** — Secrets encrypted with team key + server-side `VAULT_MASTER_KEY`; stolen DB alone is cryptographically useless
- **Secret versioning** — Full edit/delete/import history with one-click rollback
- **Bulk import** — Upload `.env`, `.csv`, or `.json` files to create secrets in one shot
- **Team management** — Create teams, invite via join keys, approve/reject requests, transfer ownership
- **Project management** — Scoped secrets per project, edit/delete by admin+
- **Audit log** — Every view, create, edit, and delete action is recorded
- **Superadmin panel** — Platform-wide oversight of all teams, projects, users, and secrets

## Tech Stack

- Python / Django
- SQLite (development)
- `cryptography` (Fernet + envelope encryption)
- HTML/CSS (custom, no framework)

## Setup

```bash
git clone https://github.com/danishskh70/SecureVault.git
cd SecureVault

python -m venv myenv
source myenv/bin/activate  # Windows: myenv\Scripts\activate

pip install -r requirements.txt
```

Create a `.env` file in the project root:

```env
VAULT_MASTER_KEY=your-random-64-char-string-here
```

> ⚠️ Never commit `.env`. This key is required to decrypt secrets — without it, the database is unreadable.

```bash
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

## Roles

| Role | Permissions |
|------|-------------|
| Owner | Everything — team settings, transfer ownership, delete projects |
| Admin | Manage members, approve requests, edit projects, view audit log |
| Developer | Create, edit, delete, import secrets |
| Viewer | Read-only access to secrets |
| Superadmin | Platform-wide access to all teams, users, and data |

## Security Model

Secrets use **envelope encryption**:
- Each team has a `Team.encryption_key` (stored in DB)
- Final decryption key = `SHA256(VAULT_MASTER_KEY + team_key)`
- Attacker needs **both** DB and server environment to decrypt anything

## Project Structure

```
secretmanager/
├── core/
│   ├── models.py             # Team, Project, Secret, Membership, AuditLog, SecretVersion
│   ├── views.py              # All views including superadmin, bulk import, versioning
│   ├── forms.py
│   ├── context_processors.py
│   └── templates/
└── secretmanager/
    └── settings.py           # Loads VAULT_MASTER_KEY from .env
```
```