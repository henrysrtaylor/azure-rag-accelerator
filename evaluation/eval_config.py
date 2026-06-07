"""Evaluation configuration and thresholds.

Defines pass/fail thresholds for each evaluation metric.
LLM-judged metrics are normalized to 0-1 scale (original 1-5 divided by 5).
"""

# LLM-judged metric thresholds (normalized 0-1 scale)
# Score of 3/5 = 0.6 normalized
THRESHOLD_GROUNDEDNESS = 0.6
THRESHOLD_RELEVANCE = 0.6
THRESHOLD_FLUENCY = 0.6
THRESHOLD_COHERENCE = 0.6

# F1 score threshold (0-1 scale)
THRESHOLD_F1 = 0.5

# Retrieval thresholds (0-1 scale)
THRESHOLD_PRECISION_AT_1 = 0.5
THRESHOLD_PRECISION_AT_5 = 0.5
THRESHOLD_RECALL_AT_1 = 0.5
THRESHOLD_RECALL_AT_5 = 0.7  # Higher for recall - missing docs is worse than extras

# Mapping of metric keys to their thresholds
METRIC_THRESHOLDS = {
    'groundedness': THRESHOLD_GROUNDEDNESS,
    'relevance': THRESHOLD_RELEVANCE,
    'fluency': THRESHOLD_FLUENCY,
    'coherence': THRESHOLD_COHERENCE,
    'f1_score': THRESHOLD_F1,
    'retrieval_precision_at_1': THRESHOLD_PRECISION_AT_1,
    'retrieval_precision_at_5': THRESHOLD_PRECISION_AT_5,
    'retrieval_recall_at_1': THRESHOLD_RECALL_AT_1,
    'retrieval_recall_at_5': THRESHOLD_RECALL_AT_5,
}
