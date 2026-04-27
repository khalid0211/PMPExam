def calculate_scores(questions: list, answers: dict) -> tuple[int, dict]:
    """Calculate total and domain-wise scores."""
    total_score = 0
    domain_scores = {}

    for question in questions:
        q_id = question["q_id"]
        domain = question["domain"]
        correct = question["correct_choice"]
        user_answer = answers.get(q_id)

        if domain not in domain_scores:
            domain_scores[domain] = {"correct": 0, "total": 0}

        domain_scores[domain]["total"] += 1

        if user_answer and user_answer.lower() == correct.lower():
            total_score += 1
            domain_scores[domain]["correct"] += 1

    return total_score, domain_scores
