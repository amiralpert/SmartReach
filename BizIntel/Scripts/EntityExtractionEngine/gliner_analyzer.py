"""
Analysis functions to read and interpret GLiNER test results
Use these functions to analyze test outputs and plan iterations
"""

import json
import csv
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from collections import Counter, defaultdict
import statistics


def analyze_latest_results(results_dir: str = "test_results") -> Dict:
    """
    Load and analyze the latest test results

    Args:
        results_dir: Directory containing test results

    Returns:
        Dictionary with analysis results
    """
    # Load JSON results
    results_file = Path(results_dir) / "gliner_test_results.json"

    if not results_file.exists():
        print(f"❌ No results found at {results_file}")
        return {}

    with open(results_file, 'r') as f:
        results = json.load(f)

    print("=" * 80)
    print("🔍 GLINER TEST ANALYSIS")
    print("=" * 80)

    # Test metadata
    metadata = results.get('test_metadata', {})
    print(f"\nTest Name: {metadata.get('test_name', 'Unknown')}")
    print(f"Timestamp: {metadata.get('timestamp', 'Unknown')}")
    print(f"Filings Tested: {metadata.get('filing_count', 0)}")

    # Overall metrics
    metrics = results.get('aggregate_metrics', {})
    if metrics:
        print(f"\n📊 Aggregate Metrics:")
        print(f"  Speed improvement: {metrics.get('average_speed_improvement', 0):.2f}x")
        print(f"  Entity reduction: {metrics.get('average_reduction_percentage', 0):.1f}%")
        print(f"  Groups formed: {metrics.get('total_groups_formed', 0)}")
        print(f"  Avg time (current): {metrics.get('average_current_time', 0):.3f}s")
        print(f"  Avg time (GLiNER): {metrics.get('average_gliner_time', 0):.3f}s")

    # Problem areas
    print(f"\n⚠️ Issues to Address:")

    issues_found = False
    for i, tc in enumerate(results.get('test_cases', []), 1):
        if not tc:
            continue

        # Check for poor normalization
        norm_analysis = tc.get('normalization_analysis', {})
        if norm_analysis.get('current_duplicate_count', 0) > 5:
            issues_found = True
            print(f"\n  Filing {i}: High duplicates ({norm_analysis['current_duplicate_count']})")
            duplicates = norm_analysis.get('current_duplicates', {})
            if duplicates:
                top_duplicates = sorted(duplicates.items(), key=lambda x: x[1], reverse=True)[:3]
                for text, count in top_duplicates:
                    print(f"    • '{text}': appears {count} times")

        # Check for slow performance
        perf = tc.get('performance', {})
        if perf.get('speed_improvement', 1) < 1:
            issues_found = True
            print(f"\n  Filing {i}: GLiNER slower than current system")
            print(f"    Current: {tc['current_system']['time_seconds']:.3f}s")
            print(f"    GLiNER: {tc['gliner_system']['time_seconds']:.3f}s")

        # Check for poor entity reduction
        if perf.get('reduction_percentage', 0) < 10:
            issues_found = True
            print(f"\n  Filing {i}: Low entity reduction ({perf['reduction_percentage']:.1f}%)")

    if not issues_found:
        print("  ✅ No major issues found!")

    # Errors
    if results.get('errors'):
        print(f"\n❌ Errors ({len(results['errors'])} total):")
        for error in results['errors'][:3]:  # Show first 3
            print(f"  • {error['error']}")

    return results


def suggest_label_improvements(results: Dict = None, results_dir: str = "test_results") -> List[str]:
    """
    Suggest label improvements based on test results

    Args:
        results: Pre-loaded results dictionary (optional)
        results_dir: Directory containing test results

    Returns:
        List of suggested label improvements
    """
    if results is None:
        results_file = Path(results_dir) / "gliner_test_results.json"
        with open(results_file, 'r') as f:
            results = json.load(f)

    print("\n" + "=" * 80)
    print("🎯 LABEL OPTIMIZATION SUGGESTIONS")
    print("=" * 80)

    suggestions = []

    # Analyze current labels
    config = results.get('test_metadata', {}).get('config', {})
    current_labels = config.get('labels', [])
    print(f"\nCurrent labels ({len(current_labels)}):")
    for label in current_labels:
        print(f"  • {label}")

    # Analyze what entities were missed
    missed_patterns = []
    low_coverage_labels = defaultdict(int)
    high_frequency_labels = defaultdict(int)

    for tc in results.get('test_cases', []):
        if not tc:
            continue

        # Compare current vs GLiNER
        current_entities = tc.get('current_system', {}).get('sample_entities', [])
        gliner_entities = tc.get('gliner_system', {}).get('sample_raw', [])

        # Find entities current system found but GLiNER missed
        current_texts = set(e.get('entity_text', '').lower() for e in current_entities)
        gliner_texts = set(e.get('text', '').lower() for e in gliner_entities)

        missed = current_texts - gliner_texts
        if missed:
            missed_patterns.extend(missed)

        # Track label usage
        for entity in gliner_entities:
            label = entity.get('label', 'Unknown')
            high_frequency_labels[label] += 1

    # Analyze missed patterns
    if missed_patterns:
        print(f"\n📉 Commonly Missed Entities:")
        missed_counter = Counter(missed_patterns)
        for text, count in missed_counter.most_common(10):
            print(f"  • '{text}': missed {count} times")

        # Suggest new labels based on missed entities
        if any('subsidiary' in m.lower() for m in missed_patterns):
            suggestions.append("Add 'Subsidiary Company' label")
        if any('acquisition' in m.lower() or 'merger' in m.lower() for m in missed_patterns):
            suggestions.append("Add 'Acquisition Target' label")
        if any('ceo' in m.lower() or 'cfo' in m.lower() or 'president' in m.lower()
              for m in missed_patterns):
            suggestions.append("Split 'Person' into 'Executive' and 'Board Member'")

    # Analyze label frequency
    if high_frequency_labels:
        print(f"\n📊 Label Usage Distribution:")
        total_entities = sum(high_frequency_labels.values())
        for label, count in sorted(high_frequency_labels.items(), key=lambda x: x[1], reverse=True):
            percentage = (count / total_entities * 100) if total_entities > 0 else 0
            print(f"  • {label}: {count} entities ({percentage:.1f}%)")

        # Check for underused labels
        for label in current_labels:
            if high_frequency_labels.get(label, 0) < total_entities * 0.01:  # Less than 1%
                suggestions.append(f"Consider removing '{label}' (low usage)")

    # Analyze normalization effectiveness
    total_groups_formed = sum(
        tc.get('normalization_analysis', {}).get('groups_formed', 0)
        for tc in results.get('test_cases', [])
    )

    if total_groups_formed < len(results.get('test_cases', [])) * 2:
        suggestions.append("Consider more specific labels to improve grouping")

    # Print suggestions
    if suggestions:
        print(f"\n💡 Recommendations:")
        for i, suggestion in enumerate(suggestions, 1):
            print(f"  {i}. {suggestion}")
    else:
        print(f"\n✅ Current labels appear to be working well")

    return suggestions


def analyze_normalization_effectiveness(results: Dict = None,
                                       results_dir: str = "test_results") -> Dict:
    """
    Detailed analysis of entity normalization performance

    Args:
        results: Pre-loaded results dictionary (optional)
        results_dir: Directory containing test results

    Returns:
        Dictionary with normalization analysis
    """
    if results is None:
        results_file = Path(results_dir) / "gliner_test_results.json"
        with open(results_file, 'r') as f:
            results = json.load(f)

    print("\n" + "=" * 80)
    print("🔄 NORMALIZATION EFFECTIVENESS ANALYSIS")
    print("=" * 80)

    analysis = {
        'total_cases': 0,
        'successful_normalizations': 0,
        'filing_company_success': 0,
        'average_group_size': 0,
        'largest_groups': [],
        'normalization_examples': []
    }

    group_sizes = []
    successful_examples = []

    for tc in results.get('test_cases', []):
        if not tc:
            continue

        analysis['total_cases'] += 1
        norm_analysis = tc.get('normalization_analysis', {})

        # Check filing company normalization
        fca = norm_analysis.get('filing_company_analysis', {})
        if fca.get('gliner_canonical'):
            if fca.get('current_variation_count', 0) > 1:
                analysis['filing_company_success'] += 1
                if len(successful_examples) < 3:  # Keep first 3 examples
                    successful_examples.append({
                        'company': fca['company_name'],
                        'variations': fca['current_variation_count'],
                        'canonical': fca['gliner_canonical'],
                        'mentions': fca['gliner_mentions']
                    })

        # Analyze group sizes
        for group in norm_analysis.get('gliner_groups', []):
            group_size = len(group.get('grouped', []))
            group_sizes.append(group_size)

            if group_size > 2:  # Significant grouping
                analysis['successful_normalizations'] += 1
                if len(analysis['largest_groups']) < 5:  # Keep top 5
                    analysis['largest_groups'].append({
                        'canonical': group['canonical'],
                        'size': group_size,
                        'examples': group['grouped'][:3]
                    })

    # Calculate statistics
    if group_sizes:
        analysis['average_group_size'] = statistics.mean(group_sizes)
        analysis['max_group_size'] = max(group_sizes)
        analysis['groups_over_2'] = sum(1 for s in group_sizes if s > 2)

    # Print analysis
    print(f"\n📊 Summary:")
    print(f"  Test cases: {analysis['total_cases']}")
    print(f"  Successful normalizations: {analysis['successful_normalizations']}")
    print(f"  Filing company success rate: "
          f"{(analysis['filing_company_success'] / analysis['total_cases'] * 100):.1f}%"
          if analysis['total_cases'] > 0 else "N/A")

    if group_sizes:
        print(f"\n📈 Group Statistics:")
        print(f"  Average group size: {analysis['average_group_size']:.1f}")
        print(f"  Maximum group size: {analysis['max_group_size']}")
        print(f"  Groups with >2 entities: {analysis['groups_over_2']}")

    if successful_examples:
        print(f"\n✅ Successful Filing Company Normalizations:")
        for ex in successful_examples:
            print(f"\n  Company: {ex['company']}")
            print(f"  Reduced {ex['variations']} variations to 1 canonical name")
            print(f"  Canonical: '{ex['canonical']}'")
            print(f"  Grouped: {ex['mentions'][:3]}{'...' if len(ex['mentions']) > 3 else ''}")

    if analysis['largest_groups']:
        print(f"\n🏆 Best Normalization Examples:")
        for group in sorted(analysis['largest_groups'], key=lambda x: x['size'], reverse=True)[:3]:
            print(f"\n  '{group['canonical']}' ({group['size']} mentions):")
            print(f"    Examples: {group['examples']}")

    return analysis


def compare_iterations(iteration1_dir: str, iteration2_dir: str) -> Dict:
    """
    Compare results between two test iterations

    Args:
        iteration1_dir: Directory for first iteration
        iteration2_dir: Directory for second iteration

    Returns:
        Dictionary with comparison results
    """
    # Load both iterations
    with open(Path(iteration1_dir) / "gliner_test_results.json", 'r') as f:
        iter1 = json.load(f)
    with open(Path(iteration2_dir) / "gliner_test_results.json", 'r') as f:
        iter2 = json.load(f)

    print("\n" + "=" * 80)
    print("📊 ITERATION COMPARISON")
    print("=" * 80)

    # Compare configurations
    config1 = iter1.get('test_metadata', {}).get('config', {})
    config2 = iter2.get('test_metadata', {}).get('config', {})

    print(f"\n🔧 Configuration Changes:")
    print(f"  Iteration 1: {config1.get('test_name', 'Unknown')}")
    print(f"  Iteration 2: {config2.get('test_name', 'Unknown')}")

    if config1.get('threshold') != config2.get('threshold'):
        print(f"  Threshold: {config1.get('threshold')} → {config2.get('threshold')}")
    if config1.get('model_size') != config2.get('model_size'):
        print(f"  Model: {config1.get('model_size')} → {config2.get('model_size')}")
    if config1.get('labels') != config2.get('labels'):
        print(f"  Labels: {len(config1.get('labels', []))} → {len(config2.get('labels', []))}")

    # Compare metrics
    metrics1 = iter1.get('aggregate_metrics', {})
    metrics2 = iter2.get('aggregate_metrics', {})

    print(f"\n📈 Performance Changes:")

    improvements = {}
    for key in ['average_speed_improvement', 'average_reduction_percentage', 'total_groups_formed']:
        val1 = metrics1.get(key, 0)
        val2 = metrics2.get(key, 0)
        change = val2 - val1
        change_pct = (change / val1 * 100) if val1 != 0 else 0

        symbol = "🔺" if change > 0 else ("🔻" if change < 0 else "➖")
        print(f"  {key.replace('_', ' ').title()}: {val1:.1f} → {val2:.1f} "
              f"{symbol} {change:+.1f} ({change_pct:+.1f}%)")

        improvements[key] = change_pct

    # Overall assessment
    print(f"\n🎯 Overall Assessment:")
    positive_improvements = sum(1 for v in improvements.values() if v > 5)
    negative_improvements = sum(1 for v in improvements.values() if v < -5)

    if positive_improvements > negative_improvements:
        print("  ✅ Iteration 2 shows overall improvement!")
    elif negative_improvements > positive_improvements:
        print("  ⚠️ Iteration 2 shows regression. Consider reverting changes.")
    else:
        print("  ➖ Performance similar between iterations.")

    return improvements


def generate_next_iteration_config(results: Dict = None,
                                  results_dir: str = "test_results") -> Dict:
    """
    Generate configuration for next iteration based on current results

    Args:
        results: Pre-loaded results dictionary (optional)
        results_dir: Directory containing test results

    Returns:
        Suggested configuration for next iteration
    """
    if results is None:
        results_file = Path(results_dir) / "gliner_test_results.json"
        with open(results_file, 'r') as f:
            results = json.load(f)

    current_config = results.get('test_metadata', {}).get('config', {})
    metrics = results.get('aggregate_metrics', {})

    print("\n" + "=" * 80)
    print("🔮 NEXT ITERATION SUGGESTIONS")
    print("=" * 80)

    # Create new config
    new_config = current_config.copy()

    # Determine iteration number
    current_name = current_config.get('test_name', 'iteration_1')
    if 'iteration_' in current_name:
        current_num = int(current_name.split('_')[1])
        new_config['test_name'] = f"iteration_{current_num + 1}_optimized"
    else:
        new_config['test_name'] = "iteration_2_optimized"

    suggestions = []

    # Threshold optimization
    if metrics.get('average_reduction_percentage', 0) < 20:
        # Not enough reduction, try lower threshold
        new_config['threshold'] = max(0.5, current_config.get('threshold', 0.7) - 0.1)
        suggestions.append(f"Lower threshold to {new_config['threshold']} for more entities")
    elif metrics.get('average_reduction_percentage', 0) > 50:
        # Too much reduction, might be missing entities
        new_config['threshold'] = min(0.9, current_config.get('threshold', 0.7) + 0.1)
        suggestions.append(f"Raise threshold to {new_config['threshold']} for better precision")

    # Model size optimization
    if metrics.get('average_speed_improvement', 1) < 2 and current_config.get('model_size') != 'small':
        new_config['model_size'] = 'small'
        suggestions.append("Switch to small model for better speed")
    elif metrics.get('average_reduction_percentage', 0) < 15 and current_config.get('model_size') != 'large':
        new_config['model_size'] = 'large'
        suggestions.append("Switch to large model for better accuracy")

    # Label optimization
    label_suggestions = suggest_label_improvements(results)
    if label_suggestions:
        # Apply some suggestions
        if "Add 'Subsidiary Company' label" in label_suggestions:
            new_config['labels'].append('Subsidiary Company')
            suggestions.append("Added 'Subsidiary Company' label")
        if "Add 'Acquisition Target' label" in label_suggestions:
            new_config['labels'].append('Acquisition Target')
            suggestions.append("Added 'Acquisition Target' label")

    print(f"\n📋 Suggested Configuration Changes:")
    for suggestion in suggestions:
        print(f"  • {suggestion}")

    print(f"\n📄 New Configuration:")
    print(f"  Test Name: {new_config['test_name']}")
    print(f"  Model: {new_config['model_size']}")
    print(f"  Threshold: {new_config['threshold']}")
    print(f"  Labels: {len(new_config['labels'])} total")

    return new_config


def export_analysis_summary(results_dir: str = "test_results",
                           output_file: str = "analysis_summary.txt") -> None:
    """
    Export comprehensive analysis summary to text file

    Args:
        results_dir: Directory containing test results
        output_file: Output file path
    """
    output_path = Path(results_dir) / output_file

    with open(output_path, 'w') as f:
        # Redirect print to file
        import sys
        original_stdout = sys.stdout
        sys.stdout = f

        print("=" * 80)
        print("GLINER TEST ANALYSIS SUMMARY")
        print("=" * 80)
        print()

        # Run all analyses
        results = analyze_latest_results(results_dir)
        print()
        suggest_label_improvements(results, results_dir)
        print()
        analyze_normalization_effectiveness(results, results_dir)
        print()
        next_config = generate_next_iteration_config(results, results_dir)

        # Restore stdout
        sys.stdout = original_stdout

    print(f"\n✅ Analysis summary exported to: {output_path}")


# Quick analysis function for command line
if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        results_directory = sys.argv[1]
    else:
        results_directory = "test_results"

    print(f"\n🔍 Analyzing results in: {results_directory}")

    # Run full analysis
    analyze_latest_results(results_directory)
    suggest_label_improvements(results_dir=results_directory)
    analyze_normalization_effectiveness(results_dir=results_directory)

    # Export summary
    export_analysis_summary(results_directory)