# Google OAuth Implementation Specification

This document details how Google OAuth authentication is implemented in the Portfolio Analysis Suite application.

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [OAuth Flow](#oauth-flow)
4. [Configuration](#configuration)
5. [Core Components](#core-components)
6. [User Management](#user-management)
7. [Permission System](#permission-system)
8. [Session State](#session-state)
9. [Database Synchronization](#database-synchronization)
10. [Security Considerations](#security-considerations)
11. [Deployment Checklist](#deployment-checklist)

---

## Overview

The application uses **Google OAuth 2.0 Authorization Code Flow** for authentication, combined with:
- **Firestore** for user profiles, roles, and permissions
- **DuckDB/MotherDuck** for synced user records in the `app_user` table
- **Streamlit session state** for maintaining authentication across page reruns

### Key OAuth Endpoints

| Endpoint | URL |
|----------|-----|
| Authorization | `https://accounts.google.com/o/oauth2/v2/auth` |
| Token Exchange | `https://oauth2.googleapis.com/token` |
| User Info | `https://www.googleapis.com/oauth2/v2/userinfo` |

### OAuth Scope

```
openid email profile
```

Requests the user's email address, display name, and profile picture.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         AUTHENTICATION LAYER                        │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────────────┐  │
│  │  Google OAuth │    │   Firestore  │    │  Streamlit Session   │  │
│  │    Provider   │    │   (Users &   │    │      State           │  │
│  │              │    │  Permissions) │    │                      │  │
│  └──────┬───────┘    └──────┬───────┘    └──────────┬───────────┘  │
│         │                   │                       │               │
│         ▼                   ▼                       ▼               │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                     utils/auth.py                            │   │
│  │               check_authentication()                         │   │
│  │               require_page_access()                          │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
├─────────────────────────────────────────────────────────────────────┤
│                         USER MANAGEMENT LAYER                        │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌──────────────────────┐    ┌──────────────────────────────────┐  │
│  │  utils/user_manager  │    │       utils/user_sync.py         │  │
│  │     (Firestore)      │    │         (DuckDB)                 │  │
│  │                      │    │                                  │  │
│  │  - ensure_user_exists│    │  - sync_authenticated_user_to_db │  │
│  │  - is_admin          │    │  - get_current_user_id           │  │
│  │  - is_super_admin    │    │  - get_current_user_info         │  │
│  │  - get_page_permission│    │                                  │  │
│  └──────────────────────┘    └──────────────────────────────────┘  │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## OAuth Flow

### Flow Diagram

```
User visits app
       │
       ▼
check_authentication() in main.py
       │
       ▼
┌──────────────────────────────────┐
│ Is 'authenticated' in session?   │
└──────────────────────────────────┘
       │
   YES │                    NO
       ▼                     │
  Return True                │
  (proceed)                  ▼
                   ┌─────────────────────────────┐
                   │ Has 'code' in URL params?   │
                   │    (Google callback)        │
                   └─────────────────────────────┘
                            │
                    YES     │           NO
                            ▼            │
           ┌────────────────────────┐    │
           │ Exchange code for token │    │
           │ POST to token endpoint  │    │
           └────────────────────────┘    │
                      │                   │
                      ▼                   │
           ┌────────────────────────┐    │
           │ Fetch user info        │    │
           │ GET userinfo endpoint  │    │
           └────────────────────────┘    │
                      │                   │
                      ▼                   │
           ┌────────────────────────┐    │
           │ ensure_user_exists()   │    │
           │ (Firestore upsert)     │    │
           └────────────────────────┘    │
                      │                   │
                      ▼                   │
           ┌────────────────────────┐    │
           │ Store in session_state │    │
           │ Clear URL params       │    │
           │ st.rerun()             │    │
           └────────────────────────┘    │
                                         │
                                         ▼
                             ┌─────────────────────┐
                             │ Show Google Sign-In │
                             │      button         │
                             └─────────────────────┘
                                         │
                                         ▼
                             User clicks → Google OAuth consent
                                         │
                                         ▼
                             Google redirects with 'code'
                                         │
                                   (loops back)
```

### Token Exchange Request

```http
POST https://oauth2.googleapis.com/token
Content-Type: application/x-www-form-urlencoded

code=<authorization_code>
&client_id=<GOOGLE_CLIENT_ID>
&client_secret=<GOOGLE_CLIENT_SECRET>
&redirect_uri=<callback_url>
&grant_type=authorization_code
```

### User Info Request

```http
GET https://www.googleapis.com/oauth2/v2/userinfo
Authorization: Bearer <access_token>
```

### Response Structure

```json
{
  "id": "123456789",
  "email": "user@example.com",
  "verified_email": true,
  "name": "User Name",
  "picture": "https://lh3.googleusercontent.com/...",
  "locale": "en"
}
```

---

## Configuration

### Secrets File Structure (`.streamlit/secrets.toml`)

```toml
[google_oauth]
client_id = "123456789.apps.googleusercontent.com"
client_secret = "GOCSPX-..."

[firestore]
type = "service_account"
project_id = "your-project-id"
private_key_id = "..."
private_key = "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
client_email = "firebase-adminsdk@your-project.iam.gserviceaccount.com"
client_id = "..."
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"
auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
client_x509_cert_url = "..."
universe_domain = "googleapis.com"

[motherduck]
token = "eyJhbGc..."
```

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `GOOGLE_CLIENT_ID` | OAuth client ID | Yes |
| `GOOGLE_CLIENT_SECRET` | OAuth client secret | Yes |
| `REDIRECT_URI` | OAuth callback URL | Optional (auto-detected) |
| `FIRESTORE_PROJECT_ID` | Firebase project ID | Optional |
| `GOOGLE_APPLICATION_CREDENTIALS` | Path to service account JSON | Optional |
| `MOTHERDUCK_TOKEN` | MotherDuck access token | For cloud DB |
| `HOSTNAME` | Deployment hostname | Optional |

### Credential Loading Priority

1. Environment variables (`GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`)
2. Streamlit secrets (`st.secrets['google_oauth']['client_id']`)
3. Empty strings (triggers setup instructions)

### Redirect URI Detection

```python
# Priority order:
1. REDIRECT_URI environment variable
2. HOSTNAME == "streamlit" → "https://portfolio-suite.streamlit.app/"
3. Default → "http://localhost:8501"
```

---

## Core Components

### `utils/auth.py`

The main authentication module containing:

#### `check_authentication() -> bool`

Main entry point for authentication. Called at the start of every page.

```python
def check_authentication():
    # 1. Initialize session state
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
        st.session_state.user_info = None
        st.session_state.user_email = None

    # 2. Quick return if already authenticated
    if st.session_state.authenticated:
        return True

    # 3. Validate credentials are configured
    # 4. Handle OAuth callback (code in URL params)
    # 5. Show login button if not authenticated
```

#### `require_page_access(page_name: str, page_title: str)`

Blocks page access if user lacks permission.

```python
def require_page_access(page_name, page_title):
    db = get_firestore_client()
    user_email = st.session_state.get('user_email')

    if not check_page_access(db, user_email, page_name):
        st.error(f"❌ Access Denied to {page_title}")
        st.info("You do not have permission to access this page.")
        st.stop()
```

#### `show_user_info_sidebar()`

Displays user avatar, name, email, and logout button in sidebar.

### `utils/firestore_client.py`

Singleton pattern for Firestore client initialization.

```python
_firestore_client = None

def get_firestore_client():
    global _firestore_client
    if _firestore_client is not None:
        return _firestore_client

    # Try initialization methods in order:
    # 1. ADC (Application Default Credentials)
    # 2. Streamlit secrets
    # 3. Service account file
    # 4. Explicit project ID

    return _firestore_client
```

---

## User Management

### `utils/user_manager.py`

Handles all user CRUD operations in Firestore.

### Firestore User Document Structure

```json
{
  "profile": {
    "email": "user@example.com",
    "name": "Display Name",
    "created_at": "timestamp",
    "last_access_date": "timestamp",
    "access_count": 42
  },
  "role": "user",
  "status": "active",
  "permissions": {
    "portfolio_management": "none",
    "file_management": "none",
    "manual_data_entry": "none",
    "project_analysis": "none",
    "portfolio_analysis": "none",
    "portfolio_charts": "none",
    "baseline_management": "none",
    "fund_tracking": "none",
    "strategic_factors": "none",
    "sdg_management": "none",
    "ai_assistant": "none",
    "database_diagnostics": "none",
    "user_management": "none"
  },
  "oauth_tokens": {
    "access_token": "...",
    "refresh_token": "...",
    "token_expiry": "timestamp",
    "token_scope": "openid email profile",
    "last_updated": "timestamp"
  },
  "database_preference": {
    "connection_type": "motherduck",
    "motherduck_database": "portfolio_cloud",
    "last_updated": "timestamp"
  }
}
```

### Bootstrap Admins

Hardcoded emails that automatically receive `super_admin` role:

```python
BOOTSTRAP_ADMINS = [
    "khalid0211@gmail.com",
    "dev@localhost"
]
```

These emails bypass normal permission checks and cannot be locked out.

### Key Functions

| Function | Description |
|----------|-------------|
| `ensure_user_exists(email, name)` | Creates or updates user on login |
| `is_admin(email)` | Returns True if role is admin/super_admin |
| `is_super_admin(email)` | Returns True if role is super_admin |
| `get_page_permission_level(email, page_name)` | Returns 'write', 'read', or 'none' |
| `check_page_access(email, page_name)` | Returns True if 'read' or 'write' |
| `can_write(email, page_name)` | Returns True if 'write' |
| `update_user_permissions(operator, target, permissions)` | Admin-only permission update |
| `set_user_role(operator, target, role)` | Admin-only role change |
| `set_user_status(operator, target, status)` | Admin-only status change |

---

## Permission System

### Roles

| Role | Description |
|------|-------------|
| `super_admin` | Full access, can manage other admins |
| `admin` | Full access to all pages |
| `user` | Access based on permissions dict |

### Status

| Status | Description |
|--------|-------------|
| `active` | Normal access |
| `suspended` | All access denied |

### Permission Levels (per page)

| Level | Description |
|-------|-------------|
| `write` | Full read/write access |
| `read` | Read-only access |
| `none` | No access (page hidden) |

### Default Permissions for New Users

All new users start with `none` on all pages. An admin must explicitly grant access.

### Permission Inheritance

`fund_tracking` inherits from `portfolio_analysis`:

```python
if page_name == 'fund_tracking':
    return get_page_permission_level(email, 'portfolio_analysis')
```

### Permission Check Hierarchy

```
1. Bootstrap admin → 'write' (always)
2. User status == 'suspended' → 'none'
3. Role == 'admin' or 'super_admin' → 'write'
4. Check permissions[page_name]
5. Default → 'none'
```

---

## Session State

### Authentication Keys

| Key | Type | Description |
|-----|------|-------------|
| `st.session_state.authenticated` | `bool` | True if logged in |
| `st.session_state.user_email` | `str` | User's email address |
| `st.session_state.user_info` | `dict` | Full OAuth user info |

### User Info Contents

```python
st.session_state.user_info = {
    "id": "123456789",
    "email": "user@example.com",
    "verified_email": True,
    "name": "User Name",
    "picture": "https://...",
    "locale": "en"
}
```

### Logout Process

```python
def logout():
    st.session_state.authenticated = False
    st.session_state.user_info = None
    st.session_state.user_email = None
    st.rerun()
```

---

## Database Synchronization

### `utils/user_sync.py`

Syncs authenticated users to DuckDB's `app_user` table.

### DuckDB User Table

```sql
CREATE TABLE app_user(
  user_id BIGINT,
  display_name VARCHAR,
  email VARCHAR,
  role VARCHAR,
  department VARCHAR,
  is_active BOOLEAN,
  created_at TIMESTAMP,
  last_login TIMESTAMP
);
```

### Sync Function

```python
def sync_authenticated_user_to_db():
    if not st.session_state.get('authenticated'):
        return None

    user_info = st.session_state.get('user_info', {})
    email = user_info.get('email')
    name = user_info.get('name')

    # Check if user exists
    existing = db.fetch_one(
        "SELECT user_id FROM app_user WHERE email = ?",
        [email]
    )

    if existing:
        return existing[0]

    # Create new user
    new_id = db.fetch_one("SELECT COALESCE(MAX(user_id), 0) + 1 FROM app_user")[0]
    db.execute("""
        INSERT INTO app_user (user_id, display_name, email, role, is_active, created_at)
        VALUES (?, ?, ?, 'User', TRUE, CURRENT_TIMESTAMP)
    """, [new_id, name, email])

    return new_id
```

---

## Security Considerations

### Strengths

- **Server-side token exchange**: Client secret never exposed to browser
- **Role-based access control**: Fine-grained page permissions
- **Bootstrap admin system**: Prevents lockout scenarios
- **Suspended status**: Can disable users without deleting
- **Firestore for sensitive data**: Separate from application database
- **Soft deletes**: Audit trail preserved

### Implemented Protections

- OAuth client secret stored server-side only
- Token exchange happens on backend
- Session state cleared on logout
- Permissions checked on every page load
- Admin-only operations require role verification

### Potential Improvements

- Implement PKCE (Proof Key for Code Exchange)
- Add token refresh logic (framework exists but not fully implemented)
- Implement rate limiting
- Add audit logging for security events
- Consider 2FA for admin accounts

---

## Deployment Checklist

### 1. Google Cloud Console Setup

- [ ] Create new project
- [ ] Enable Google OAuth 2.0 API
- [ ] Create OAuth 2.0 credentials (Web application type)
- [ ] Add authorized redirect URIs:
  - `http://localhost:8501` (local development)
  - `https://your-app.streamlit.app/` (Streamlit Cloud)
  - `https://your-domain.com/` (custom domain)

### 2. Firebase Setup

- [ ] Create Firebase project (can reuse Google Cloud project)
- [ ] Enable Firestore database
- [ ] Create service account with `roles/datastore.user` IAM role
- [ ] Download service account JSON

### 3. Configure Secrets

- [ ] Create `.streamlit/secrets.toml` from template
- [ ] Add OAuth client ID and secret
- [ ] Add Firestore service account credentials
- [ ] Add MotherDuck token (if using cloud database)

### 4. Bootstrap Admin

- [ ] Ensure at least one email in `BOOTSTRAP_ADMINS` list
- [ ] First login creates user with `super_admin` role
- [ ] Super admin can then grant access to other users

### 5. Test Authentication Flow

- [ ] Run `streamlit run main.py`
- [ ] Click "Sign in with Google"
- [ ] Verify redirect to Google consent screen
- [ ] Verify redirect back with user logged in
- [ ] Check user created in Firestore
- [ ] Check user synced to DuckDB `app_user` table
- [ ] Verify logout clears session

---

## File Reference

```
utils/
├── auth.py              # OAuth flow, check_authentication(), require_page_access()
├── user_manager.py      # Firestore user CRUD, permissions, roles
├── firestore_client.py  # Singleton Firestore client
├── user_sync.py         # DuckDB user synchronization
├── database_config.py   # User database preferences
└── portfolio_access.py  # Portfolio-level access control

.streamlit/
└── secrets.toml         # OAuth & Firestore credentials

main.py                  # Entry point, calls check_authentication()

pages/
├── 1_*.py               # Each page calls check_authentication() + require_page_access()
└── 11_User_Management.py # Admin-only user management UI
```

---

## Quick Reference

### Protect a New Page

```python
from utils.auth import check_authentication, require_page_access

# At the top of your page file:
if not check_authentication():
    st.stop()

require_page_access('page_permission_key', 'Page Display Title')

# Page content follows...
```

### Check Write Permission

```python
from utils.user_manager import can_write

user_email = st.session_state.get('user_email')
if can_write(db, user_email, 'portfolio_management'):
    st.button("Save Changes")
```

### Get Current User

```python
from utils.user_sync import get_current_user_id, get_current_user_info

user_id = get_current_user_id()  # DuckDB user_id
user_info = get_current_user_info()  # Full DuckDB record
```

---

*Last updated: April 2026*
