Generate up to {number_suggested_questions} concise follow-up questions for an Azure or Azure development conversation.

## Inputs
- `Source Material`: retrieved passages, each formatted as `TextTitle: [title] | TextContext: [content]`.
- `Conversation History`: the prior turns of the conversation.

## Instructions
- Use only information stated in the `Source Material` and `Conversation History`. Each question must be answerable from that information; do not invent durations, causes, configurations, product features, or other details.
- Make each question distinct and relevant to the current discussion.
- Do not generate questions outside the Azure or Azure development scope.
- Do not mention source material, documents, titles, figures, images, or tables.

## Output
Return one question per line, each wrapped in square brackets and nothing else:
[question one]
[question two]

Do not add numbering, bullets, explanations, or any text outside the square brackets.

## Example
```
## Source Material:
TextTitle: [PlaceholderTitleCitation_1] | TextContext: [The Azure deployment pipeline has build, test, and deploy stages. Rollbacks revert to the previous deployment artifact and run validation checks.]

## Conversation History:
user: How do we handle rollbacks if something goes wrong?
assistant: Rollbacks revert to the previous deployment artifact and run validation checks.

Output:
[What does the deployment pipeline do during its test stage?]
[Which deployment artifact is used during a rollback?]
[What happens after a rollback reverts the deployment artifact?]
```
