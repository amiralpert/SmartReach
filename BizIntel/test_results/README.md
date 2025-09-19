# GLiNER Test Results

This directory contains test results from GLiNER entity extraction testing.

## Files Generated

- **gliner_test_results.json** - Detailed test results in JSON format for analysis
- **gliner_test_report.md** - Human-readable test report with summary and examples
- **gliner_comparison.csv** - CSV file with metrics for spreadsheet analysis
- **test_samples/** - Individual test case files for debugging

## Analyzing Results

Use the analysis functions in `EntityExtractionEngine.gliner_analyzer`:

```python
from EntityExtractionEngine import analyze_latest_results, suggest_label_improvements

# Analyze latest test results
results = analyze_latest_results()

# Get suggestions for next iteration
suggestions = suggest_label_improvements()
```

## Iteration Process

1. Run Cell 4 in the notebook to generate test results
2. Check GitHub for the generated files in this directory
3. Analyze results and modify `gliner_config.py` based on findings
4. Re-run Cell 4 with updated configuration
5. Repeat until optimal performance is achieved