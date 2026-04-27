import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore

@st.cache_resource
def get_db():
    """Initialize Firebase and return Firestore client."""
    if not firebase_admin._apps:
        try:
            cred_dict = dict(st.secrets["firebase"])
            cred = credentials.Certificate(cred_dict)
            firebase_admin.initialize_app(cred)
        except Exception as e:
            st.error(f"Error initializing Firebase: {e}")
            return None
    return firestore.client()
