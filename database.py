import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore

def init_db():
    """Initializes the Firebase connection using Streamlit secrets."""
    # Check if a Firebase app has already been initialized to avoid errors
    if not firebase_admin._apps:
        # Construct the credential dictionary from secrets.toml
        key_dict = {
            "type": st.secrets["firebase"]["type"],
            "project_id": st.secrets["firebase"]["project_id"],
            "private_key_id": st.secrets["firebase"]["private_key_id"],
            "private_key": st.secrets["firebase"]["private_key"].replace("\\n", "\n"),
            "client_email": st.secrets["firebase"]["client_email"],
            "client_id": st.secrets["firebase"]["client_id"],
            "auth_uri": st.secrets["firebase"]["auth_uri"],
            "token_uri": st.secrets["firebase"]["token_uri"],
            "auth_provider_x509_cert_url": st.secrets["firebase"]["auth_provider_x509_cert_url"],
            "client_x509_cert_url": st.secrets["firebase"]["client_x509_cert_url"],
        }
        
        cred = credentials.Certificate(key_dict)
        firebase_admin.initialize_app(cred)
        
    return firestore.client()

# Create the database client object
db = init_db()