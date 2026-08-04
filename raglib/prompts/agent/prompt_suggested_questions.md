Generate up to {number_suggested_questions} concise follow-up questions for an Azure or Azure development conversation.

Use only information stated in the conversation history and source text. Each question must be answerable from that information; do not invent durations, causes, configurations, product features, or other details.

Make each question distinct and relevant to the current discussion. Do not mention source text, documents, titles, figures, images, or tables. Do not generate questions outside the Azure or Azure development scope.

Return only one question per line, using exactly this format:
[question one]
[question two]

Do not add numbering, bullets, explanations, or text outside the square brackets.

Example:
Source text:
The Azure deployment pipeline has build, test, and deploy stages. Rollbacks revert to the previous deployment artifact and run validation checks.

Conversation history:
user: How do we handle rollbacks if something goes wrong?
assistant: Rollbacks revert to the previous deployment artifact and run validation checks.

Output:
[What does the deployment pipeline do during its test stage?]
[Which deployment artifact is used during a rollback?]
[What happens after a rollback reverts the deployment artifact?]
