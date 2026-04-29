import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore

@st.cache_resource
def get_db():
    """Initialize Firebase and return Firestore client."""
    if not firebase_admin._apps:
        try:
            cred_dict = dict(st.secrets["firebase"])
            # Streamlit secrets may contain escaped newlines for private keys.
            if "private_key" in cred_dict and isinstance(cred_dict["private_key"], str):
                cred_dict["private_key"] = cred_dict["private_key"].replace("\\n", "\n")
            cred = credentials.Certificate(cred_dict)
            firebase_admin.initialize_app(cred)
        except Exception as e:
            st.error(f"Error initializing Firebase: {e}")
            return None
    return firestore.client()
