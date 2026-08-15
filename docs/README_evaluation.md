# Evaluation

This accelerator uses **custom LLM-as-judge evaluators** rather than the Azure AI Evaluation SDK. This approach provides full control over prompts, scoring rubrics, and avoids SDK compatibility issues with newer models.

## Metrics

### LLM-Judged (1-5 scale, normalized to 0-1)

| Metric | Description |
|--------|-------------|
| **Groundedness** | Is the response grounded in the provided context? |
| **Relevance** | Does the response address the user's query? |
| **Coherence** | Is the response logically structured and easy to follow? |
| **Fluency** | Is the response grammatically correct and natural? |

### Retrieval Metrics (0-1 scale)

| Metric | Description |
|--------|-------------|
| **Precision@k** | Of the top k retrieved docs, how many are relevant? |
| **Recall@k** | Of all relevant docs, how many appear in top k? |
| **F1 Score** | Harmonic mean of precision and recall |

## Architecture

```
evaluation/
└── evaluation_script.py   # Main evaluation runner

data/
└── golden_dataset.json    # Test queries with ground truth

raglib/
├── eval.py                # Judge functions and metrics
├── config.py              # Typed app settings and evaluation thresholds
└── prompts/evaluation/    # LLM judge prompts
    ├── prompt_eval_groundedness.md
    ├── prompt_eval_relevance.md
    ├── prompt_eval_coherence.md
    └── prompt_eval_fluency.md
```

## How It Works

1. **Load golden dataset** - queries with expected answers and relevant documents
2. **Run RAG pipeline** - call `RAGPipeline.run_evaluation()` with each query's chat history and security filter to get the response and retrieved document context
3. **LLM judges** - call judge model to score groundedness, relevance, coherence, fluency
4. **Retrieval metrics** - calculate precision/recall from retrieved vs. expected docs
5. **Aggregate & report** - average scores, compare to thresholds, output results

## Judge Prompts

Each judge prompt defines:
- **Role** - what the evaluator is assessing
- **Rubric** - 5-level scoring criteria with labels (Very Poor → Excellent)
- **Output format** - JSON with `score` (1-5) and `reasoning`
- **Examples** - concrete scoring examples

Prompts live in `raglib/prompts/evaluation/` and can be customized.

## Configuration

Thresholds are defined by the frozen `EvalConfig` dataclass in
`raglib/config.py` and exposed through the `eval_config` instance:

```python
@dataclass(frozen=True)
class EvalConfig:
    groundedness_threshold: float = 0.6
    relevance_threshold: float = 0.6
    f1_score_threshold: float = 0.5
    retrieval_recall_at_5_threshold: float = 0.7


eval_config = EvalConfig()
```

## Judge Model

Set `judge_model` in the `AppConfig` dataclass in `raglib/config.py`. The judge model can differ from the main chat model.

## Running

```bash
python evaluation/evaluation_script.py
```

Outputs:
- Console summary table with pass/fail per metric
- `evaluation/results/<timestamp>/full_results.json` - per-query details
- `evaluation/results/<timestamp>/summary.json` - aggregated metrics
