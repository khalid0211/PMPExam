import streamlit as st
import requests
from urllib.parse import urlencode
from firebase_config import get_db
from config import ADMIN_EMAIL, SessionKeys, UserRole

# OAuth 2.0 Endpoints
GOOGLE_AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_ENDPOINT = "https://www.googleapis.com/oauth2/v2/userinfo"
OAUTH_SCOPE = "openid email profile"


def _get_oauth_credentials() -> tuple:
    """Get OAuth credentials from secrets.

    Returns:
        tuple: (client_id, client_secret, redirect_uri)
    """
    try:
        client_id = st.secrets["google_oauth"]["client_id"]
        client_secret = st.secrets["google_oauth"]["client_secret"]
        redirect_uri = st.secrets["google_oauth"]["redirect_uri"]
    except KeyError:
        # Fallback to old [auth] section
        client_id = st.secrets["auth"]["client_id"]
        client_secret = st.secrets["auth"]["client_secret"]
        redirect_uri = st.secrets["auth"]["redirect_uri"].replace("/oauth2callback", "")
    return client_id, client_secret, redirect_uri


def _get_authorization_url() -> str:
    """Generate Google OAuth authorization URL."""
    client_id, _, redirect_uri = _get_oauth_credentials()

    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": OAUTH_SCOPE,
        "access_type": "offline",
        "prompt": "select_account",
    }
    return f"{GOOGLE_AUTH_ENDPOINT}?{urlencode(params)}"


def _exchange_code_for_token(code: str) -> dict | None:
    """Exchange authorization code for access token.

    Args:
        code: Authorization code from Google callback

    Returns:
        dict with access_token, or None on failure
    """
    client_id, client_secret, redirect_uri = _get_oauth_credentials()

    data = {
        "code": code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
    }

    try:
        response = requests.post(GOOGLE_TOKEN_ENDPOINT, data=data, timeout=10)
        if response.status_code == 200:
            return response.json()
        else:
            st.error(f"Token exchange failed: {response.status_code} - {response.text}")
            return None
    except requests.RequestException as e:
        st.error(f"Token exchange error: {e}")
        return None


def _fetch_user_info(access_token: str) -> dict | None:
    """Fetch user info from Google using access token.

    Args:
        access_token: Valid OAuth access token

    Returns:
        dict with user info (id, email, name, picture), or None on failure
    """
    headers = {"Authorization": f"Bearer {access_token}"}

    try:
        response = requests.get(GOOGLE_USERINFO_ENDPOINT, headers=headers, timeout=10)
        if response.status_code == 200:
            return response.json()
        else:
            st.error(f"User info fetch failed: {response.status_code}")
            return None
    except requests.RequestException as e:
        st.error(f"User info fetch error: {e}")
        return None


def _handle_oauth_callback() -> dict | None:
    """Handle OAuth callback when 'code' is in URL params.

    Returns:
        User info dict if successful, None otherwise
    """
    query_params = st.query_params
    code = query_params.get("code")

    if not code:
        return None

    # Exchange code for token
    token_data = _exchange_code_for_token(code)
    if not token_data:
        # Clear the code param so user can retry
        st.query_params.clear()
        return None

    access_token = token_data.get("access_token")
    if not access_token:
        st.error("No access token in response")
        st.query_params.clear()
        return None

    # Fetch user info
    user_info = _fetch_user_info(access_token)
    if not user_info:
        st.query_params.clear()
        return None

    # Clear URL params
    st.query_params.clear()

    return user_info


def _normalize_user_payload(user: dict, email: str, uid: str) -> dict:
    """Backfill required fields for older/incomplete user records."""
    is_admin = email.lower() == ADMIN_EMAIL.lower()
    normalized = dict(user or {})
    normalized["uid"] = normalized.get("uid") or uid
    normalized["email"] = normalized.get("email") or email
    normalized["is_enabled"] = normalized.get("is_enabled", is_admin)
    normalized["max_tries"] = normalized.get("max_tries", 3)
    normalized["current_tries"] = normalized.get("current_tries", 0)
    normalized["role"] = normalized.get("role") or (UserRole.ADMIN if is_admin else UserRole.STUDENT)
    return normalized


def handle_login():
    """Handle Google OAuth login flow with local development support."""
    # Check if running locally
    is_local = st.secrets.get("app", {}).get("is_local", False)

    if is_local:
        st.sidebar.info("Running in Local Dev Mode")
        mock_user = {
            "email": ADMIN_EMAIL,
            "id": "local_dev_user_123",
            "name": ADMIN_EMAIL.split("@")[0],
            "picture": None,
        }
        user, _ = get_or_create_user(mock_user["email"], mock_user["id"])
        user["name"] = mock_user["name"]
        user["picture"] = mock_user["picture"]
        st.session_state[SessionKeys.USER] = user
        return user

    # Check if already authenticated (user in session)
    if SessionKeys.USER in st.session_state:
        return st.session_state[SessionKeys.USER]

    # Handle OAuth callback (code in URL params)
    user_info = _handle_oauth_callback()
    if user_info:
        email = user_info.get("email")
        uid = user_info.get("id") or user_info.get("sub") or email
        name = user_info.get("name")
        picture = user_info.get("picture")

        if not email:
            st.error("Could not retrieve email from Google. Please try again.")
            return None

        try:
            user, is_new_user = get_or_create_user(email, uid)
        except Exception as e:
            st.error(f"Sign-in succeeded, but user profile initialization failed: {e}")
            return None

        if not user:
            st.error("Database connection could not be initialized. Please try again.")
            return None

        user["name"] = name or user.get("email", email).split("@")[0]
        user["picture"] = picture

        if not user.get("is_enabled", False):
            st.title("PMP Exam Simulator")
            st.image("PMPExamBanner.jpg", width=800)
            if is_new_user:
                st.info("Your account has been created, please wait for the administrator to enable your access to the Exam Simulator.")
            else:
                st.info("Please wait for the administrator to enable your access to the Exam Simulator.")
            if st.button("Logout"):
                logout()
            return None

        st.session_state[SessionKeys.USER] = user
        st.rerun()

    # Not logged in - show login UI
    st.title("PMP Exam Simulator")
    st.image("PMPExamBanner.jpg", width=800)
    st.write("Please sign in to continue.")

    try:
        authorization_url = _get_authorization_url()
        st.link_button("Sign in with Google", authorization_url, type="primary")
    except Exception as e:
        st.error(f"Could not generate login URL: {e}")
        st.caption("Please check your OAuth configuration in Streamlit Cloud secrets.")

    return None


def get_or_create_user(email: str, uid: str) -> tuple[dict, bool]:
    """Get existing user or create new one in Firestore.

    Returns:
        tuple: (user_dict, was_just_created)
    """
    db = get_db()
    if not db:
        return {}, False

    user_ref = db.collection("users").document(uid)
    user_doc = user_ref.get()

    if user_doc.exists:
        existing_user = user_doc.to_dict() or {}
        normalized = _normalize_user_payload(existing_user, email, uid)
        if normalized != existing_user:
            user_ref.set(normalized, merge=True)
        return normalized, False

    # Create new user
    new_user = _normalize_user_payload({}, email, uid)
    if new_user["role"] == UserRole.STUDENT:
        new_user["is_enabled"] = False
    user_ref.set(new_user)
    return new_user, True


def logout():
    """Clear session and logout."""
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()
