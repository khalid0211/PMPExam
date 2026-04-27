# Technical Specifications: MCQ Exam Application

## 1. Project Overview
A Streamlit-based web application for conducting Multiple Choice Question (MCQ) exams. The system uses Firebase (Firestore & Auth) for data persistence and Google Authentication for user access.

## 2. Architecture & Tech Stack
- **Frontend:** Streamlit
- **Backend/Database:** Google Firebase (Firestore)
- **Authentication:** Google OAuth2 (Firebase Auth)
- **Data Processing:** Pandas (for CSV and scoring aggregation)

## 3. Data Schema (Firestore)

### Users Collection
- `uid` (string): Unique identifier from Google Auth.
- `email` (string): User's email.
- `is_enabled` (bool): Admin-controlled access toggle.
- `max_tries` (int): Maximum allowed exam attempts.
- `current_tries` (int): Number of attempts used.
- `role` (string): 'admin' or 'student'.

### QuestionBank Collection
- `q_id` (string): Unique ID.
- `text` (string): The question text.
- `domain` (string): Category (e.g., Math, Science).
- `choices` (map): {a, b, c, d}.
- `correct_choice` (string): 'a', 'b', 'c', or 'd'.

### Exams Collection
- `exam_id` (string): Unique ID.
- `user_id` (string): Reference to user.
- `start_time` (timestamp).
- `end_time` (timestamp/null).
- `status` (string): 'in-progress' | 'completed'.
- `total_score` (int).
- `domain_scores` (map): {domain_name: score}.
- `answers` (map): {q_id: selected_choice}.

## 4. Feature Requirements

### 4.1 Authentication & Authorization
- Login via Google Auth.
- Validation: Check `is_enabled` status in Firestore.
- Access Control: If `is_enabled` is false, block access to exams.

### 4.2 Student Workflow
- **Dashboard:** View previous exam stats (Total score, Domain scores, Time taken).
- **Exam Creation:** Create new exam if `current_tries < max_tries`.
- **Exam Engine:**
    - Questions presented in random order.
    - Navigation: [Previous], [Next], [Mark for Review].
    - Sidebar navigation to jump to specific questions.
    - Confirm before [Submit].
- **Review Mode:** Detailed view of a specific exam with "Correct/Incorrect" ticks and a "Show Correct Answer" button.

### 4.3 Admin Workflow
- **User Management:** List all students, toggle access, and reset attempt counters.
- **Content Management:** Upload CSV to populate/update the Question Bank.
    - Required CSV columns: `question, domain, a, b, c, d, correct_choice`.

## 5. UI/UX Specifications
- Use `st.session_state` to ensure the exam persists through Streamlit reruns.
- The exam interface should be clean, focusing on one question at a time.
- Display a progress bar for the exam completion status.
