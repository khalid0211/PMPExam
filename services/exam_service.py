from datetime import datetime, timezone
from firebase_config import get_db
from config import ExamStatus, EXAM_DURATION_SECONDS
from google.cloud.firestore_v1.base_query import FieldFilter
import uuid

class ExamService:
    def __init__(self):
        self.db = get_db()
        self.collection = self.db.collection("exams") if self.db else None

    def create_exam(self, user_id: str, questions: list) -> str:
        if not self.collection:
            return ""
            
        exam_id = str(uuid.uuid4())
        question_ids = [q["q_id"] for q in questions]

        exam_data = {
            "exam_id": exam_id,
            "user_id": user_id,
            "start_time": datetime.now(timezone.utc),
            "end_time": None,
            "status": ExamStatus.IN_PROGRESS,
            "total_score": 0,
            "domain_scores": {},
            "answers": {},
            "time_remaining": EXAM_DURATION_SECONDS,
            "question_order": question_ids
        }

        self.collection.document(exam_id).set(exam_data)
        return exam_id

    def get_exam(self, exam_id: str) -> dict:
        if not self.collection:
            return {}
        doc = self.collection.document(exam_id).get()
        return doc.to_dict() if doc.exists else {}

    def get_in_progress_exam(self, user_id: str) -> dict:
        if not self.collection:
            return None
        docs = (self.collection
                .where(filter=FieldFilter("user_id", "==", user_id))
                .where(filter=FieldFilter("status", "==", ExamStatus.IN_PROGRESS))
                .limit(1)
                .stream())
        for doc in docs:
            return doc.to_dict()
        return None

    def save_answer(self, exam_id: str, question_id: str, answer: str):
        if self.collection:
            self.collection.document(exam_id).update({
                f"answers.{question_id}": answer
            })

    def save_all_answers(self, exam_id: str, answers: dict):
        """Save all answers in a single Firestore call."""
        if self.collection and answers:
            self.collection.document(exam_id).update({
                "answers": answers
            })

    def save_answer_deltas(self, exam_id: str, answers: dict, question_ids: set):
        """Persist only changed answers to keep writes fast as exam grows."""
        if not self.collection or not answers or not question_ids:
            return
        updates = {}
        for qid in question_ids:
            if qid in answers:
                updates[f"answers.{qid}"] = answers[qid]
        if updates:
            self.collection.document(exam_id).update(updates)

    def update_time_remaining(self, exam_id: str, time_remaining: int):
        if self.collection:
            self.collection.document(exam_id).update({
                "time_remaining": time_remaining
            })

    def complete_exam(self, exam_id: str, total_score: int,
                      domain_scores: dict, answers: dict):
        if self.collection:
            self.collection.document(exam_id).update({
                "status": ExamStatus.COMPLETED,
                "end_time": datetime.now(timezone.utc),
                "total_score": total_score,
                "domain_scores": domain_scores,
                "answers": answers
            })

    def delete_exam(self, exam_id: str):
        if self.collection:
            self.collection.document(exam_id).delete()

    def delete_all_exams(self) -> int:
        """Delete all exam documents. Returns count of deleted exams."""
        if not self.collection:
            return 0
        deleted = 0
        docs = self.collection.stream()
        batch = self.db.batch()
        for doc in docs:
            batch.delete(doc.reference)
            deleted += 1
            if deleted % 400 == 0:
                batch.commit()
                batch = self.db.batch()
        batch.commit()
        return deleted

    def get_user_exams(self, user_id: str) -> list:
        if not self.collection:
            return []
        docs = self.collection.where(filter=FieldFilter("user_id", "==", user_id)).stream()
        exams = [doc.to_dict() for doc in docs]
        return sorted(exams, key=lambda x: x.get("start_time", 0), reverse=True)

    def get_all_exams(self) -> list:
        if not self.collection:
            return []
        docs = self.collection.stream()
        exams = [doc.to_dict() for doc in docs]
        return sorted(exams, key=lambda x: x.get("start_time", 0), reverse=True)
