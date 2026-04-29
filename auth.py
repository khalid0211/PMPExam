import streamlit as st
import traceback
from firebase_config import get_db
from config import ADMIN_EMAIL, SessionKeys, UserRole

def _run_firebase_health_check():
    """Run lightweight checks for Firebase configuration and Firestore access."""
    required_keys = [
        "type",
        "project_id",
        "private_key_id",
        "private_key",
        "client_email",
        "client_id",
        "auth_uri",
        "token_uri",
        "auth_provider_x509_cert_url",
        "client_x509_cert_url",
    ]
    firebase_secrets = st.secrets.get("firebase", {})
    missing = [k for k in required_keys if not firebase_secrets.get(k)]
    if missing:
        st.error("Firebase secrets are missing required keys.")
        st.caption(f"Missing keys: {', '.join(missing)}")
        return

    db = get_db()
    if not db:
        st.error("Firebase initialization failed.")
        return

    try:
        # Read-only probe to validate Firestore connectivity and permissions.
        db.collection("users").limit(1).get()
        st.success("Firebase and Firestore connectivity look healthy.")
        st.caption("Initialization succeeded and a Firestore read completed.")
    except Exception as e:
        st.error("Firestore read check failed.")
        st.caption(f"Firestore error details: {e}")

def _read_user_field(user_obj, field, default=None):
    """Read auth fields from both object-style and dict-style user payloads."""
    try:
        if isinstance(user_obj, dict):
            return user_obj.get(field, default)
    except Exception:
        pass
    try:
        return getattr(user_obj, field)
    except Exception:
        pass
    try:
        return user_obj[field]
    except Exception:
        return default


def _get_streamlit_user_info():
    """Support both legacy and current Streamlit auth APIs."""
    # Newer API
    user = getattr(st, "user", None)
    if user is not None:
        is_logged_in = bool(_read_user_field(user, "is_logged_in", False))
        if is_logged_in:
            email = _read_user_field(user, "email")
            # Different runtimes may expose id as "id" or "sub"
            uid = _read_user_field(user, "id") or _read_user_field(user, "sub")
            name = _read_user_field(user, "name") or _read_user_field(user, "given_name")
            picture = (
                _read_user_field(user, "picture")
                or _read_user_field(user, "picture_url")
                or _read_user_field(user, "avatar_url")
            )
            if email:
                return {
                    "is_logged_in": True,
                    "email": email,
                    "id": uid or email,
                    "name": name,
                    "picture": picture
                }

    # Legacy API
    exp_user = getattr(st, "experimental_user", None)
    if exp_user is not None:
        is_logged_in = bool(_read_user_field(exp_user, "is_logged_in", False))
        if is_logged_in:
            email = _read_user_field(exp_user, "email")
            uid = _read_user_field(exp_user, "id") or _read_user_field(exp_user, "sub")
            name = _read_user_field(exp_user, "name") or _read_user_field(exp_user, "given_name")
            picture = (
                _read_user_field(exp_user, "picture")
                or _read_user_field(exp_user, "picture_url")
                or _read_user_field(exp_user, "avatar_url")
            )
            if email:
                return {
                    "is_logged_in": True,
                    "email": email,
                    "id": uid or email,
                    "name": name,
                    "picture": picture
                }

    return {"is_logged_in": False}


def _trigger_streamlit_login():
    """Handle Streamlit login API differences across versions."""
    login_fn = getattr(st, "login", None)
    if login_fn is None:
        raise RuntimeError("Streamlit login API is unavailable in this runtime.")
    # Use simple login() call - works with flat [auth] config (single provider)
    login_fn()

def _render_auth_debug_panel():
    """Render inline Streamlit auth diagnostics on the login screen."""
    user_obj = getattr(st, "user", None)
    auth_cfg = st.secrets.get("auth", {})
    st.write(
        {
            "streamlit_version": getattr(st, "__version__", "unknown"),
            "has_login": callable(getattr(st, "login", None)),
            "has_logout": callable(getattr(st, "logout", None)),
            "has_user_api": user_obj is not None,
            "auth_secrets_present": "auth" in st.secrets,
            "has_client_id": bool(auth_cfg.get("client_id")),
            "has_client_secret": bool(auth_cfg.get("client_secret")),
            "has_redirect_uri": bool(auth_cfg.get("redirect_uri")),
            "has_cookie_secret": bool(auth_cfg.get("cookie_secret")),
            "user_is_logged_in": bool(_read_user_field(user_obj, "is_logged_in", False)) if user_obj else False,
            "user_email": _read_user_field(user_obj, "email") if user_obj else None,
        }
    )

    c1, c2 = st.columns(2)
    with c1:
        if st.button("Debug: Trigger st.login()", key="debug_login_btn"):
            try:
                _trigger_streamlit_login()
            except Exception as e:
                st.error("Debug login failed.")
                st.code(f"{type(e).__name__}: {e}")
                st.code(traceback.format_exc())
    with c2:
        if st.button("Debug: Trigger st.logout()", key="debug_logout_btn"):
            try:
                logout_fn = getattr(st, "logout", None)
                if logout_fn is None:
                    st.error("st.logout() is unavailable in this runtime.")
                else:
                    logout_fn()
            except Exception as e:
                st.error("Debug logout failed.")
                st.code(f"{type(e).__name__}: {e}")
                st.code(traceback.format_exc())

def _validate_auth_secrets_shape():
    """Return a human-readable validation message for auth secrets."""
    auth = st.secrets.get("auth", {})
    has_credentials = bool(auth.get("client_id")) and bool(auth.get("client_secret"))
    has_common = bool(auth.get("redirect_uri")) and bool(auth.get("cookie_secret"))
    has_metadata = bool(auth.get("server_metadata_url"))

    if not has_common:
        return "Missing required [auth] keys: redirect_uri and/or cookie_secret."
    if not has_credentials:
        return "Missing [auth] credentials: client_id and/or client_secret."
    if not has_metadata:
        return "Missing [auth] server_metadata_url."
    return "Auth secrets configured correctly (flat format)."

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
    # check if running locally or on Streamlit Cloud
    is_local = st.secrets.get("app", {}).get("is_local", False)

    if is_local:
        st.sidebar.info("Running in Local Dev Mode")
        # Mock user for local testing
        mock_user = {
            "email": ADMIN_EMAIL,
            "id": "local_dev_user_123",
            "name": ADMIN_EMAIL.split("@")[0],
            "picture": None,
            "is_logged_in": True
        }
        user = get_or_create_user(mock_user["email"], mock_user["id"])
        user["name"] = mock_user["name"]
        user["picture"] = mock_user["picture"]
        st.session_state[SessionKeys.USER] = user
        return user

    # Production Streamlit Cloud Auth
    user_info = _get_streamlit_user_info()
    if not user_info.get("is_logged_in", False):
        st.title("PMP Exam Simulator")
        st.image("PMPExamBanner.jpg", use_column_width=True)
        st.write("Please sign in to continue.")
        if st.button("Open Auth Debug Panel", key="open_auth_debug_btn"):
            st.session_state["show_auth_debug"] = not st.session_state.get("show_auth_debug", False)
        if st.session_state.get("show_auth_debug", False):
            with st.expander("Auth Debug Panel", expanded=True):
                _render_auth_debug_panel()
        with st.expander("Troubleshoot Firebase / Login", expanded=False):
            st.caption("Use this if Google sign-in returns an internal server error.")
            if st.button("Run Firebase Health Check", key="firebase_health_btn"):
                _run_firebase_health_check()
        if st.button("Sign in with Google", type="primary"):
            try:
                _trigger_streamlit_login()
            except Exception as e:
                st.error(
                    "Google login failed. Verify Streamlit Cloud authentication is enabled and app secrets are correct."
                )
                st.warning(_validate_auth_secrets_shape())
                st.code(f"{type(e).__name__}: {e}")
                st.caption(f"Auth error details: {e}")
                st.code(traceback.format_exc())
        return None

    try:
        user = get_or_create_user(user_info["email"], user_info["id"])
    except Exception as e:
        st.error("Sign-in succeeded, but user profile initialization failed.")
        st.caption(f"Initialization error details: {e}")
        return None

    if not user:
        st.error(
            "Sign-in succeeded, but database connection could not be initialized. "
            "Please verify Firebase secrets in Streamlit Cloud and try again."
        )
        return None

    user["name"] = user_info.get("name") or user.get("email", user_info["email"]).split("@")[0]
    user["picture"] = user_info.get("picture")

    if not user.get("is_enabled", False):
        st.error("Your account is disabled. Contact administrator.")
        if st.button("Logout"):
            st.logout()
        return None

    st.session_state[SessionKeys.USER] = user
    return user

def get_or_create_user(email: str, uid: str) -> dict:
    """Get existing user or create new one in Firestore."""
    db = get_db()
    if not db:
        return {}
        
    user_ref = db.collection("users").document(uid)
    user_doc = user_ref.get()

    if user_doc.exists:
        existing_user = user_doc.to_dict() or {}
        normalized = _normalize_user_payload(existing_user, email, uid)
        # Persist backfilled fields so future logins are stable.
        if normalized != existing_user:
            user_ref.set(normalized, merge=True)
        return normalized

    # Create new user
    new_user = _normalize_user_payload({}, email, uid)
    # New students require admin approval before they can access exams.
    if new_user["role"] == UserRole.STUDENT:
        new_user["is_enabled"] = False
    user_ref.set(new_user)
    return new_user

def logout():
    """Clear session and logout."""
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.logout()
