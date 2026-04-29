import streamlit as st
import traceback

st.set_page_config(page_title="Auth Debug", page_icon=":lock:", layout="centered")
st.title("Streamlit Auth Debug")
st.caption("Use this page to isolate OAuth callback issues from app business logic.")


def _read_user_field(user_obj, field, default=None):
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


def _safe_user_snapshot():
    user = getattr(st, "user", None)
    if user is None:
        return {"api": "st.user unavailable", "is_logged_in": False}
    return {
        "api": "st.user",
        "is_logged_in": bool(_read_user_field(user, "is_logged_in", False)),
        "email": _read_user_field(user, "email"),
        "id": _read_user_field(user, "id") or _read_user_field(user, "sub"),
        "name": _read_user_field(user, "name") or _read_user_field(user, "given_name"),
    }


with st.expander("Environment Snapshot", expanded=True):
    st.write(
        {
            "streamlit_version": getattr(st, "__version__", "unknown"),
            "has_login": callable(getattr(st, "login", None)),
            "has_logout": callable(getattr(st, "logout", None)),
            "has_user_api": getattr(st, "user", None) is not None,
            "auth_secrets_present": "auth" in st.secrets,
            "auth_secret_keys": list(st.secrets.get("auth", {}).keys()) if "auth" in st.secrets else [],
        }
    )

st.subheader("Auth Actions")
col1, col2 = st.columns(2)
with col1:
    if st.button("Sign in with Google", type="primary"):
        try:
            login_fn = getattr(st, "login", None)
            if login_fn is None:
                st.error("st.login() is unavailable in this runtime.")
            else:
                login_fn()
        except TypeError:
            try:
                # Backward compatibility with older auth API shape.
                st.login("google")
            except Exception as e:
                st.error("Login invocation failed.")
                st.code(f"{type(e).__name__}: {e}")
                st.code(traceback.format_exc())
        except Exception as e:
            st.error("Login invocation failed.")
            st.code(f"{type(e).__name__}: {e}")
            st.code(traceback.format_exc())

with col2:
    if st.button("Logout"):
        try:
            logout_fn = getattr(st, "logout", None)
            if logout_fn is None:
                st.error("st.logout() is unavailable in this runtime.")
            else:
                logout_fn()
        except Exception as e:
            st.error("Logout failed.")
            st.code(f"{type(e).__name__}: {e}")
            st.code(traceback.format_exc())

st.subheader("Current User State")
try:
    st.json(_safe_user_snapshot())
except Exception as e:
    st.error("Could not read user state.")
    st.code(f"{type(e).__name__}: {e}")
    st.code(traceback.format_exc())

st.info(
    "If this page still returns Internal server error after Google account selection, "
    "the issue is in Streamlit Cloud auth runtime/config, not your app logic."
)
