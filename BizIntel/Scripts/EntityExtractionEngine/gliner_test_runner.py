"""
GLiNER Test Runner with GitHub-visible output
Allows iteration without notebook changes
"""

import json
import csv
import os
import subprocess
from datetime import datetime
from typing import Dict, List, Optional
import time
from collections import Counter

# Import configurations
from .gliner_config import GLINER_CONFIG
from .gliner_extractor import GLiNEREntityExtractor
from . import (
    EntityExtractionPipeline,
    get_unprocessed_filings,
    get_filing_sections,
    get_db_connection
)
from .logging_utils import log_info, log_warning, log_error


class GLiNERTestRunner:
    """Orchestrates GLiNER testing with output to files for GitHub visibility"""

    def __init__(self, output_dir: str = None):
        """
        Initialize test runner

        Args:
            output_dir: Directory for test outputs (auto-detected if None)
        """
        # Smart path selection for Kaggle vs local environment
        if output_dir is None:
            if os.path.exists("/kaggle/working/SmartReach"):
                # In Kaggle: save directly to repo directory
                output_dir = "/kaggle/working/SmartReach/BizIntel/test_results"
            else:
                # Local: use relative path
                output_dir = "test_results"

        self.output_dir = output_dir
        self.ensure_output_dirs()
        self.test_timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    def ensure_output_dirs(self):
        """Create output directories if they don't exist"""
        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs(f"{self.output_dir}/test_samples", exist_ok=True)
        print(f"📁 Test results will be saved to: {os.path.abspath(self.output_dir)}")

    def run_and_save_results(self, custom_config: Dict = None) -> Dict:
        """
        Main test execution with file output

        Args:
            custom_config: Optional config overrides

        Returns:
            Dictionary with all test results
        """
        # Use custom config or default
        config = custom_config or GLINER_CONFIG

        print(f"\n{'='*80}")
        print(f"🚀 GLiNER TEST RUN - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*80}")
        print(f"Test Name: {config['test_name']}")
        print(f"Model: {config['model_size']} | Threshold: {config['threshold']}")
        print(f"Testing {config['test_filing_limit']} filings")

        # Get test filings
        print(f"\n📋 Loading test filings...")
        filings = self._get_test_filings(config['test_filing_limit'])

        if not filings:
            print("❌ No filings available for testing")
            return {}

        print(f"✅ Loaded {len(filings)} filings")

        # Initialize systems
        print(f"\n🔧 Initializing extraction systems...")

        # Current 4-model system
        current_pipeline = EntityExtractionPipeline(self._get_pipeline_config())

        # GLiNER system
        try:
            gliner_pipeline = GLiNEREntityExtractor(
                model_size=config['model_size'],
                labels=config['labels'],
                threshold=config['threshold'],
                debug=config['output'].get('verbose', False)
            )
            print(f"✅ GLiNER model loaded successfully")
        except Exception as e:
            print(f"❌ Failed to load GLiNER: {e}")
            return {}

        # Run tests
        all_results = {
            "test_metadata": {
                "timestamp": datetime.now().isoformat(),
                "test_name": config['test_name'],
                "config": config,
                "filing_count": len(filings)
            },
            "test_cases": [],
            "aggregate_metrics": {},
            "errors": []
        }

        print(f"\n🏃 Running entity extraction tests...")
        print("-" * 60)

        for i, filing in enumerate(filings, 1):
            print(f"\n[{i}/{len(filings)}] Testing: {filing.get('company_domain', 'Unknown')}")

            try:
                test_case = self._test_single_filing(
                    filing,
                    current_pipeline,
                    gliner_pipeline,
                    config
                )

                all_results["test_cases"].append(test_case)

                # Save individual test case if configured
                if config.get('save_individual_samples', True):
                    self._save_test_case(test_case, i)

                # Print progress
                if test_case:
                    print(f"  ✓ Current: {test_case['current_system']['entity_count']} entities")
                    print(f"  ✓ GLiNER:  {test_case['gliner_system']['normalized_group_count']} groups")
                    print(f"  ✓ Speed:   {test_case['performance']['speed_improvement']:.2f}x")

            except Exception as e:
                error_msg = f"Failed to test filing {i}: {str(e)}"
                print(f"  ❌ {error_msg}")
                all_results["errors"].append({
                    "filing_index": i,
                    "error": error_msg
                })

        # Calculate aggregate metrics
        print(f"\n📊 Calculating aggregate metrics...")
        all_results["aggregate_metrics"] = self._calculate_aggregate_metrics(
            all_results["test_cases"]
        )

        # Save all outputs
        print(f"\n💾 Saving test results...")
        self._save_json_results(all_results)
        self._save_markdown_report(all_results)
        self._save_csv_comparison(all_results)

        # Auto-commit results to GitHub
        print(f"\n📁 Files saved to: {self.output_dir}")
        self._commit_results_to_github()

        # Print summary
        self._print_summary(all_results)

        return all_results

    def _get_test_filings(self, limit: int) -> List[Dict]:
        """Get filings for testing"""
        try:
            # Get connection function
            def get_connection():
                return get_db_connection(self._get_neon_config())

            # Get unprocessed filings
            filings = get_unprocessed_filings(get_connection, limit=limit)
            return filings

        except Exception as e:
            log_error("TestRunner", f"Failed to get test filings: {e}")
            # Return empty list if database not available
            return []

    def _get_neon_config(self) -> Dict:
        """Get Neon database configuration"""
        try:
            from kaggle_secrets import UserSecretsClient
            user_secrets = UserSecretsClient()
            return {
                'host': user_secrets.get_secret("NEON_HOST"),
                'database': user_secrets.get_secret("NEON_DATABASE"),
                'user': user_secrets.get_secret("NEON_USER"),
                'password': user_secrets.get_secret("NEON_PASSWORD")
            }
        except ImportError:
            # For local testing
            from .local_secrets import SECRETS
            return {
                'host': SECRETS.get("NEON_HOST"),
                'database': SECRETS.get("NEON_DATABASE"),
                'user': SECRETS.get("NEON_USER"),
                'password': SECRETS.get("NEON_PASSWORD")
            }

    def _get_pipeline_config(self) -> Dict:
        """Get configuration for current pipeline"""
        return {
            'models': {
                'confidence_threshold': 0.75,
                'warm_up_enabled': False,
            },
            'entity_extraction': {
                'max_chunk_size': 2000,
                'chunk_overlap': 200,
                'max_chunks_per_section': 50,
                'enable_chunking': True
            }
        }

    def _test_single_filing(self, filing: Dict, current_pipeline,
                          gliner_pipeline, config: Dict) -> Dict:
        """Test one filing with both systems"""

        filing_info = {
            "accession": filing.get('accession_number', 'Unknown'),
            "type": filing.get('filing_type', 'Unknown'),
            "company": filing.get('company_domain', 'Unknown')
        }

        # Get filing text
        sections = get_filing_sections(
            filing['accession_number'],
            filing.get('filing_type'),
            section_cache=None,
            config=config
        )

        test_text = ""
        section_name = "Unknown"

        if sections:
            # Use first non-empty section up to max length
            for sec_name, sec_text in sections.items():
                if sec_text and len(sec_text.strip()) > 100:
                    test_text = sec_text[:config['max_text_length']]
                    section_name = sec_name
                    break

        if not test_text:
            test_text = "No text available for this filing"

        filing_context = {
            'company_name': filing.get('company_domain', ''),
            'filing_type': filing.get('filing_type', ''),
            'accession': filing.get('accession_number', '')
        }

        # Current system extraction
        print(f"  Running current system...")
        start = time.time()
        try:
            current_entities = current_pipeline.extract_entities(test_text)
        except Exception as e:
            print(f"    Warning: Current system error: {e}")
            current_entities = []
        current_time = time.time() - start

        # GLiNER extraction
        print(f"  Running GLiNER...")
        start = time.time()
        try:
            gliner_raw = gliner_pipeline.extract_entities(test_text)
            gliner_normalized = gliner_pipeline.extract_with_normalization(
                test_text,
                filing_context
            )
        except Exception as e:
            print(f"    Warning: GLiNER error: {e}")
            gliner_raw = []
            gliner_normalized = []
        gliner_time = time.time() - start

        # Analyze normalization impact
        normalization_analysis = self._analyze_normalization(
            current_entities,
            gliner_raw,
            gliner_normalized,
            filing_context
        )

        return {
            "filing": filing_info,
            "section_used": section_name,
            "text_sample": test_text[:500] + "..." if len(test_text) > 500 else test_text,
            "current_system": {
                "entity_count": len(current_entities),
                "unique_entities": len(set(e.get('entity_text', '') for e in current_entities)),
                "time_seconds": current_time,
                "sample_entities": current_entities[:10] if current_entities else []
            },
            "gliner_system": {
                "raw_entity_count": len(gliner_raw),
                "normalized_group_count": len(gliner_normalized),
                "time_seconds": gliner_time,
                "sample_raw": gliner_raw[:10] if gliner_raw else [],
                "sample_normalized": gliner_normalized[:5] if gliner_normalized else []
            },
            "normalization_analysis": normalization_analysis,
            "performance": {
                "speed_improvement": current_time / gliner_time if gliner_time > 0 else 0,
                "entity_reduction": len(current_entities) - len(gliner_normalized),
                "reduction_percentage": ((len(current_entities) - len(gliner_normalized)) /
                                       len(current_entities) * 100)
                                      if len(current_entities) > 0 else 0
            }
        }

    def _analyze_normalization(self, current: List[Dict], gliner_raw: List[Dict],
                              gliner_normalized: List[Dict], filing_context: Dict) -> Dict:
        """Analyze how well GLiNER normalized entities"""

        # Find potential duplicates in current system
        current_texts = [e.get('entity_text', '').lower() for e in current]
        text_counts = Counter(current_texts)

        duplicates = {text: count for text, count in text_counts.items() if count > 1}

        # Check GLiNER groupings
        grouped_correctly = []
        for norm_group in gliner_normalized:
            mentions = norm_group.get('mentions', [])
            if len(mentions) > 1:
                grouped_correctly.append({
                    "canonical": norm_group.get('canonical_name', ''),
                    "grouped": [m.get('text', '') for m in mentions],
                    "count": len(mentions)
                })

        # Check filing company normalization
        filing_company_analysis = {}
        if filing_context.get('company_name'):
            company_core = filing_context['company_name'].lower().split('.')[0]

            # Current system variations
            current_company_variations = [
                e.get('entity_text', '') for e in current
                if company_core in e.get('entity_text', '').lower() or
                e.get('entity_text', '').lower() in ['company', 'the company']
            ]

            # GLiNER normalization
            gliner_filing_company = None
            for group in gliner_normalized:
                if group.get('label') == 'Filing Company':
                    gliner_filing_company = group
                    break

            filing_company_analysis = {
                "company_name": filing_context['company_name'],
                "current_variations": list(set(current_company_variations)),
                "current_variation_count": len(current_company_variations),
                "gliner_canonical": gliner_filing_company.get('canonical_name', '')
                                  if gliner_filing_company else None,
                "gliner_mentions": [m.get('text', '') for m in
                                  gliner_filing_company.get('mentions', [])]
                                 if gliner_filing_company else []
            }

        return {
            "current_duplicates": duplicates,
            "current_duplicate_count": sum(duplicates.values()) - len(duplicates)
                                      if duplicates else 0,
            "gliner_groups": grouped_correctly,
            "groups_formed": len(grouped_correctly),
            "filing_company_analysis": filing_company_analysis
        }

    def _calculate_aggregate_metrics(self, test_cases: List[Dict]) -> Dict:
        """Calculate overall metrics"""

        if not test_cases:
            return {}

        valid_cases = [tc for tc in test_cases if tc and 'performance' in tc]

        if not valid_cases:
            return {}

        metrics = {
            "test_count": len(valid_cases),

            "average_speed_improvement": sum(
                tc['performance']['speed_improvement'] for tc in valid_cases
            ) / len(valid_cases),

            "average_entity_reduction": sum(
                tc['performance']['entity_reduction'] for tc in valid_cases
            ) / len(valid_cases),

            "average_reduction_percentage": sum(
                tc['performance']['reduction_percentage'] for tc in valid_cases
            ) / len(valid_cases),

            "total_current_entities": sum(
                tc['current_system']['entity_count'] for tc in valid_cases
            ),

            "total_gliner_groups": sum(
                tc['gliner_system']['normalized_group_count'] for tc in valid_cases
            ),

            "total_groups_formed": sum(
                tc['normalization_analysis']['groups_formed'] for tc in valid_cases
            ),

            "average_current_time": sum(
                tc['current_system']['time_seconds'] for tc in valid_cases
            ) / len(valid_cases),

            "average_gliner_time": sum(
                tc['gliner_system']['time_seconds'] for tc in valid_cases
            ) / len(valid_cases),

            "filing_company_normalization_success": sum(
                1 for tc in valid_cases
                if tc['normalization_analysis'].get('filing_company_analysis', {}).get('gliner_canonical')
            )
        }

        return metrics

    def _save_json_results(self, results: Dict):
        """Save detailed JSON for analysis"""
        output_file = f"{self.output_dir}/gliner_test_results.json"
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        print(f"  📄 JSON results saved: {output_file}")

    def _save_markdown_report(self, results: Dict):
        """Save human-readable markdown report"""
        output_file = f"{self.output_dir}/gliner_test_report.md"

        with open(output_file, 'w') as f:
            # Header
            f.write(f"# GLiNER Test Report\n\n")
            f.write(f"**Generated**: {results['test_metadata']['timestamp']}\n")
            f.write(f"**Test Name**: {results['test_metadata']['test_name']}\n\n")

            # Configuration
            config = results['test_metadata']['config']
            f.write("## Configuration\n\n")
            f.write(f"- **Model**: `{config['model_size']}`\n")
            f.write(f"- **Threshold**: `{config['threshold']}`\n")
            f.write(f"- **Labels**: {len(config['labels'])} labels\n")
            f.write(f"  - {', '.join(config['labels'][:5])}...\n\n")

            # Overall Performance
            metrics = results.get('aggregate_metrics', {})
            if metrics:
                f.write("## Overall Performance\n\n")
                f.write(f"- **Test Cases**: {metrics.get('test_count', 0)}\n")
                f.write(f"- **Speed Improvement**: {metrics.get('average_speed_improvement', 0):.2f}x faster\n")
                f.write(f"- **Entity Reduction**: {metrics.get('average_reduction_percentage', 0):.1f}%\n")
                f.write(f"- **Groups Formed**: {metrics.get('total_groups_formed', 0)} total\n")
                f.write(f"- **Avg Time (Current)**: {metrics.get('average_current_time', 0):.3f}s\n")
                f.write(f"- **Avg Time (GLiNER)**: {metrics.get('average_gliner_time', 0):.3f}s\n\n")

            # Individual Test Cases
            f.write("## Test Case Details\n\n")
            for i, tc in enumerate(results.get('test_cases', [])[:10], 1):  # First 10
                if not tc:
                    continue

                f.write(f"### Test {i}: {tc['filing']['company']}\n\n")
                f.write(f"- **Filing**: `{tc['filing']['accession']}`\n")
                f.write(f"- **Type**: {tc['filing']['type']}\n")
                f.write(f"- **Section**: {tc.get('section_used', 'Unknown')}\n\n")

                f.write("**Results**:\n")
                f.write(f"- Current System: {tc['current_system']['entity_count']} entities "
                       f"({tc['current_system']['unique_entities']} unique)\n")
                f.write(f"- GLiNER: {tc['gliner_system']['raw_entity_count']} raw → "
                       f"{tc['gliner_system']['normalized_group_count']} groups\n")
                f.write(f"- Speed: {tc['performance']['speed_improvement']:.2f}x faster\n")
                f.write(f"- Reduction: {tc['performance']['reduction_percentage']:.1f}%\n\n")

                # Normalization examples
                if tc['normalization_analysis']['gliner_groups']:
                    f.write("**Normalization Examples**:\n")
                    for group in tc['normalization_analysis']['gliner_groups'][:3]:
                        f.write(f"- `{group['canonical']}`: "
                               f"{group['grouped'][:3]}{'...' if len(group['grouped']) > 3 else ''}\n")
                    f.write("\n")

                # Filing company normalization
                fca = tc['normalization_analysis'].get('filing_company_analysis', {})
                if fca and fca.get('gliner_canonical'):
                    f.write("**Filing Company Normalization**:\n")
                    f.write(f"- Current variations: {fca['current_variation_count']}\n")
                    f.write(f"- GLiNER canonical: `{fca['gliner_canonical']}`\n")
                    f.write(f"- Grouped mentions: {len(fca['gliner_mentions'])}\n\n")

            # Errors
            if results.get('errors'):
                f.write("## Errors\n\n")
                for error in results['errors']:
                    f.write(f"- Filing {error['filing_index']}: {error['error']}\n")

        print(f"  📝 Markdown report saved: {output_file}")

    def _save_csv_comparison(self, results: Dict):
        """Save CSV for spreadsheet analysis"""
        output_file = f"{self.output_dir}/gliner_comparison.csv"

        with open(output_file, 'w', newline='') as f:
            fieldnames = [
                'filing', 'company', 'filing_type', 'section',
                'current_entities', 'current_unique', 'gliner_raw', 'gliner_groups',
                'speed_improvement', 'entity_reduction', 'reduction_percent',
                'groups_formed', 'current_time', 'gliner_time'
            ]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            for tc in results.get('test_cases', []):
                if not tc:
                    continue

                writer.writerow({
                    'filing': tc['filing']['accession'],
                    'company': tc['filing']['company'],
                    'filing_type': tc['filing']['type'],
                    'section': tc.get('section_used', 'Unknown'),
                    'current_entities': tc['current_system']['entity_count'],
                    'current_unique': tc['current_system']['unique_entities'],
                    'gliner_raw': tc['gliner_system']['raw_entity_count'],
                    'gliner_groups': tc['gliner_system']['normalized_group_count'],
                    'speed_improvement': f"{tc['performance']['speed_improvement']:.2f}",
                    'entity_reduction': tc['performance']['entity_reduction'],
                    'reduction_percent': f"{tc['performance']['reduction_percentage']:.1f}",
                    'groups_formed': tc['normalization_analysis']['groups_formed'],
                    'current_time': f"{tc['current_system']['time_seconds']:.3f}",
                    'gliner_time': f"{tc['gliner_system']['time_seconds']:.3f}"
                })

        print(f"  📊 CSV comparison saved: {output_file}")

    def _save_test_case(self, test_case: Dict, index: int):
        """Save individual test case for debugging"""
        output_file = f"{self.output_dir}/test_samples/sample_{index:03d}.json"
        with open(output_file, 'w') as f:
            json.dump(test_case, f, indent=2, default=str)

    def _print_summary(self, results: Dict):
        """Print test summary"""
        print(f"\n{'='*80}")
        print(f"📈 TEST SUMMARY")
        print(f"{'='*80}")

        metrics = results.get('aggregate_metrics', {})
        if metrics:
            print(f"\n🎯 Key Results:")
            print(f"  • Speed: {metrics.get('average_speed_improvement', 0):.2f}x faster")
            print(f"  • Reduction: {metrics.get('average_reduction_percentage', 0):.1f}% fewer entities")
            print(f"  • Normalization: {metrics.get('total_groups_formed', 0)} groups created")

            if metrics.get('average_speed_improvement', 0) > 2:
                print(f"\n✅ GLiNER shows significant speed improvement!")
            if metrics.get('average_reduction_percentage', 0) > 30:
                print(f"✅ GLiNER effectively reduces entity duplication!")

        print(f"\n📁 Results saved to: {self.output_dir}/")
        print(f"  • gliner_test_results.json")
        print(f"  • gliner_test_report.md")
        print(f"  • gliner_comparison.csv")

        if results.get('errors'):
            print(f"\n⚠️ {len(results['errors'])} errors occurred during testing")

    def _commit_results_to_github(self):
        """Auto-commit test results to GitHub for persistence"""
        try:
            print("\n🔄 Committing results to GitHub...")

            # Navigate to the repository root
            repo_path = "/kaggle/working/SmartReach/BizIntel" if os.path.exists("/kaggle/working/SmartReach") else os.getcwd()

            # Git commands to add and commit the test results (no error suppression)
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')
            commands = [
                f"cd {repo_path} && git add test_results/gliner_test_results.json test_results/gliner_test_report.md test_results/gliner_comparison.csv",
                f"cd {repo_path} && git commit -m 'GLiNER test results - {timestamp}\n\nAutomatically committed by GLiNER test runner\nTest results saved for analysis and comparison'",
                f"cd {repo_path} && git push origin main"
            ]

            # Execute git commands with proper error handling
            all_successful = True
            for i, cmd in enumerate(commands):
                result = subprocess.run(cmd, shell=True, capture_output=True, text=True)

                if result.returncode != 0:
                    all_successful = False
                    # Check for common non-error conditions
                    if "nothing to commit" in result.stdout or "nothing to commit" in result.stderr:
                        print("  ℹ️ No changes to commit (results may already exist)")
                        break
                    else:
                        # Real error occurred
                        from .logging_utils import log_warning
                        log_warning("GLiNER", f"Git {['add', 'commit', 'push'][i]} failed: {result.stderr}")
                        print(f"  ⚠️ Git {['add', 'commit', 'push'][i]} failed: {result.stderr.strip()}")
                        break

            # Report final status
            if all_successful:
                print("  ✅ Results committed and pushed to GitHub")
                print("  📊 Results available at: https://github.com/amiralpert/SmartReach/tree/main/BizIntel/test_results")
            else:
                print(f"  💡 Manual commit needed - files saved to: {self.output_dir}/")

        except Exception as e:
            # Don't fail the test if Git operations fail
            from .logging_utils import log_warning
            log_warning("GLiNER", f"Could not auto-commit results to GitHub: {e}")
            print(f"  ⚠️ Could not auto-commit to GitHub: {e}")
            print(f"  💡 You can manually commit the results from {self.output_dir}/")
            print(f"  📂 Files should be visible at: {os.path.abspath(self.output_dir)}")