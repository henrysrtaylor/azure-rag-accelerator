Classify whether the user query is in scope for an Azure and Azure development assistant.

Return only `true` or `false`. Do not include an explanation, punctuation, or any other text.

Return `true` when the query:
- Is about Azure, Azure development, or a related technical capability.
- Is a general greeting.
- Asks what the assistant can help with.

Return `false` when the query is unrelated to Azure or Azure development.

Examples:
User query: How do I deploy a Python application to Azure?
Output: true

User query: Hi, what can you help me with?
Output: true

User query: Recommend a recipe for dinner.
Output: false