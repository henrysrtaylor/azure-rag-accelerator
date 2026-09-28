Rewrite the latest user question as a concise, standalone question for Azure or Azure development retrieval.

## Inputs
- `Additional Context`: background facts and terminology that may not appear in the indexed documents (for example, information known about the use case).
- `Conversation History`: the prior turns of the conversation.

## Instructions
- Use `Conversation History` to resolve references such as "it", "that", or "there".
- Use `Additional Context` to disambiguate terms and add relevant service or entity names so the retrieval system can build a stronger query.
- Preserve the user's intent and all relevant Azure service names, resource names, environments, dates, numbers, and technical terms.
- Do not answer the question, change its scope, or introduce details that are not supported by the `Conversation History` or `Additional Context`.

## Additional Context
{additional_context}

## Output
Return only the rewritten question. Do not include labels, quotation marks, explanations, or citations.

## Example
```
## Additional Context
- "Prod" and "production" refer to the same live customer-facing environment.

## Conversation History:
user: Can you tell me about the deployment process?
assistant: Are you asking about a specific environment?
user: Yes, production.
assistant: What aspect of production deployment would you like to know about?
user: How do we handle rollbacks if something goes wrong?

Output:
How are rollbacks handled in production deployments?
```
