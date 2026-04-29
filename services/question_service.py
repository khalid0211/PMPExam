import pandas as pd
import random
import streamlit as st
from firebase_config import get_db

class QuestionService:
    def __init__(self):
        self.db = get_db()
        self.collection = self.db.collection("question_bank") if self.db else None

    def get_all_questions(self) -> list:
        if not self.collection:
            return []
        docs = self.collection.stream()
        return [{"q_id": doc.id, **doc.to_dict()} for doc in docs]

    def get_questions_by_ids(self, question_ids: list) -> list:
        """Fetch only the specified questions by their IDs."""
        if not self.collection or not question_ids:
            return []
        # Firestore 'in' queries are limited to 30 items, so batch if needed
        questions = []
        batch_size = 30
        for i in range(0, len(question_ids), batch_size):
            batch_ids = question_ids[i:i + batch_size]
            docs = self.collection.where("__name__", "in", batch_ids).stream()
            questions.extend([{"q_id": doc.id, **doc.to_dict()} for doc in docs])
        return questions

    def get_randomized_questions(self) -> list:
        questions = self.get_all_questions()
        random.shuffle(questions)
        return questions

    def upload_from_csv(self, df: pd.DataFrame) -> tuple[int, int]:
        """Upload questions from user's CSV format."""
        if not self.db:
            return 0, 0
            
        success, errors = 0, 0
        batch = self.db.batch()
        
        # Expected columns: SNo.,Domain,Question,Option A,Option B,Option C,Option D,Correct Answer
        for idx, row in df.iterrows():
            try:
                # Use SNo or index as ID
                sno = str(row.get("SNo.", idx))
                q_id = f"q_{sno}"
                doc_ref = self.collection.document(q_id)

                question_data = {
                    "text": str(row["Question"]),
                    "domain": str(row["Domain"]),
                    "choices": {
                        "a": str(row["Option A"]),
                        "b": str(row["Option B"]),
                        "c": str(row["Option C"]),
                        "d": str(row["Option D"])
                    },
                    "correct_choice": str(row["Correct Answer"]).strip().lower()
                }
                batch.set(doc_ref, question_data)
                success += 1
                
                # Firestore batch limit is 500
                if success % 400 == 0:
                    batch.commit()
                    batch = self.db.batch()
                    
            except Exception as e:
                print(f"Error uploading row {idx}: {e}")
                errors += 1

        batch.commit()
        return success, errors

    def clear_all_questions(self):
        if not self.collection:
            return
        docs = self.collection.stream()
        batch = self.db.batch()
        count = 0
        for doc in docs:
            batch.delete(doc.reference)
            count += 1
            if count % 400 == 0:
                batch.commit()
                batch = self.db.batch()
        batch.commit()
