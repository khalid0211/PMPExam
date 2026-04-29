from firebase_config import get_db


class SettingsService:
    def __init__(self):
        self.db = get_db()
        self.collection = self.db.collection("app_settings") if self.db else None
        self.doc_id = "review"

    def get_review_settings(self) -> dict:
        default = {"detailed_review_enabled": False}
        if not self.collection:
            return default
        doc = self.collection.document(self.doc_id).get()
        if not doc.exists:
            return default
        data = doc.to_dict() or {}
        return {
            "detailed_review_enabled": bool(data.get("detailed_review_enabled", False))
        }

    def set_detailed_review_enabled(self, enabled: bool):
        if not self.collection:
            return
        self.collection.document(self.doc_id).set(
            {"detailed_review_enabled": bool(enabled)},
            merge=True
        )
