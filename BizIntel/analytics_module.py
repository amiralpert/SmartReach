"""
Analytics module for querying and analyzing stored relationships
"""
import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import pandas as pd
import logging

logger = logging.getLogger(__name__)

class RelationshipAnalytics:
    """Query and analyze stored semantic relationships"""
    
    def __init__(self, db_manager):
        self.db = db_manager
    
    async def get_company_overview(self, company_domain: str) -> Dict:
        """Get comprehensive relationship overview for a company"""
        async with self.db.acquire() as conn:
            # Get relationship summary
            summary = await conn.fetchrow("""
                SELECT 
                    COUNT(DISTINCT bucket_id) as total_relationships,
                    COUNT(DISTINCT entity_name) as unique_entities,
                    COUNT(DISTINCT relationship_type) as relationship_types,
                    AVG(avg_confidence_score) as avg_confidence,
                    MIN(first_mentioned_date) as earliest_mention,
                    MAX(last_mentioned_date) as latest_mention
                FROM system_uno.relationship_buckets
                WHERE company_domain = $1 AND is_active = TRUE
            """, company_domain)
            
            # Get relationships by type
            by_type = await conn.fetch("""
                SELECT 
                    relationship_type,
                    COUNT(*) as count,
                    AVG(avg_confidence_score) as avg_confidence
                FROM system_uno.relationship_buckets
                WHERE company_domain = $1 AND is_active = TRUE
                GROUP BY relationship_type
                ORDER BY count DESC
            """, company_domain)
            
            # Get top entities
            top_entities = await conn.fetch("""
                SELECT 
                    entity_name,
                    COUNT(DISTINCT relationship_type) as relationship_count,
                    MAX(master_semantic_summary) as latest_summary,
                    SUM(total_monetary_value) as total_value
                FROM system_uno.relationship_buckets
                WHERE company_domain = $1 AND is_active = TRUE
                GROUP BY entity_name
                ORDER BY relationship_count DESC
                LIMIT 10
            """, company_domain)
            
            return {
                'company': company_domain,
                'summary': dict(summary) if summary else {},
                'relationships_by_type': [dict(r) for r in by_type],
                'top_entities': [dict(e) for e in top_entities]
            }
    
    async def search_relationships(self, 
                                  query: str,
                                  company_domain: Optional[str] = None,
                                  relationship_type: Optional[str] = None,
                                  min_confidence: float = 0.5) -> List[Dict]:
        """Search relationships using semantic summaries"""
        async with self.db.acquire() as conn:
            conditions = ["to_tsvector('english', semantic_summary) @@ plainto_tsquery('english', $1)"]
            params = [query]
            param_count = 1
            
            if company_domain:
                param_count += 1
                conditions.append(f"b.company_domain = ${param_count}")
                params.append(company_domain)
            
            if relationship_type:
                param_count += 1
                conditions.append(f"b.relationship_type = ${param_count}")
                params.append(relationship_type)
            
            param_count += 1
            conditions.append(f"e.confidence_score >= ${param_count}")
            params.append(min_confidence)
            
            where_clause = " AND ".join(conditions)
            
            results = await conn.fetch(f"""
                SELECT 
                    e.semantic_summary,
                    e.semantic_action,
                    e.semantic_impact,
                    e.filing_date,
                    e.confidence_score,
                    b.company_domain,
                    b.entity_name,
                    b.relationship_type,
                    b.master_semantic_summary
                FROM system_uno.relationship_semantic_events e
                JOIN system_uno.relationship_buckets b ON e.bucket_id = b.bucket_id
                WHERE {where_clause}
                ORDER BY e.confidence_score DESC, e.filing_date DESC
                LIMIT 50
            """, *params)
            
            return [dict(r) for r in results]
    
    async def get_temporal_evolution(self, 
                                    company_domain: str,
                                    entity_name: str,
                                    relationship_type: str) -> List[Dict]:
        """Get temporal evolution of a specific relationship"""
        async with self.db.acquire() as conn:
            # Get bucket
            bucket = await conn.fetchrow("""
                SELECT bucket_id, master_semantic_summary
                FROM system_uno.relationship_buckets
                WHERE company_domain = $1 
                AND entity_name = $2 
                AND relationship_type = $3
            """, company_domain, entity_name, relationship_type)
            
            if not bucket:
                return []
            
            # Get all events
            events = await conn.fetch("""
                SELECT 
                    filing_date,
                    semantic_summary,
                    semantic_action,
                    semantic_impact,
                    monetary_value,
                    percentage_value,
                    mentioned_time_period,
                    confidence_score
                FROM system_uno.relationship_semantic_events
                WHERE bucket_id = $1
                ORDER BY filing_date ASC
            """, bucket['bucket_id'])
            
            return {
                'master_summary': bucket['master_semantic_summary'],
                'timeline': [dict(e) for e in events]
            }
    
    async def get_high_impact_relationships(self, 
                                           company_domain: Optional[str] = None,
                                           days_back: int = 90) -> List[Dict]:
        """Get high-impact relationships from recent filings"""
        async with self.db.acquire() as conn:
            conditions = [
                "e.semantic_impact IN ('positive', 'negative')",
                "e.confidence_score > 0.7",
                f"e.filing_date > CURRENT_DATE - INTERVAL '{days_back} days'"
            ]
            params = []
            
            if company_domain:
                conditions.append("b.company_domain = $1")
                params.append(company_domain)
            
            where_clause = " AND ".join(conditions)
            
            query = f"""
                SELECT 
                    b.company_domain,
                    b.entity_name,
                    b.relationship_type,
                    e.semantic_summary,
                    e.semantic_impact,
                    e.monetary_value,
                    e.business_impact_summary,
                    e.filing_date,
                    e.confidence_score
                FROM system_uno.relationship_semantic_events e
                JOIN system_uno.relationship_buckets b ON e.bucket_id = b.bucket_id
                WHERE {where_clause}
                ORDER BY 
                    CASE WHEN e.monetary_value IS NOT NULL THEN e.monetary_value ELSE 0 END DESC,
                    e.confidence_score DESC
                LIMIT 20
            """
            
            results = await conn.fetch(query, *params) if params else await conn.fetch(query)
            
            return [dict(r) for r in results]
    
    async def get_relationship_network(self, company_domain: str) -> Dict:
        """Get network of relationships for visualization"""
        async with self.db.acquire() as conn:
            # Get all relationships
            relationships = await conn.fetch("""
                SELECT 
                    entity_name,
                    relationship_type,
                    total_mentions,
                    avg_confidence_score,
                    master_semantic_summary
                FROM system_uno.relationship_buckets
                WHERE company_domain = $1 AND is_active = TRUE
            """, company_domain)
            
            # Build network structure
            nodes = set()
            edges = []
            
            nodes.add(company_domain)
            
            for rel in relationships:
                entity = rel['entity_name']
                nodes.add(entity)
                
                edges.append({
                    'source': company_domain,
                    'target': entity,
                    'type': rel['relationship_type'],
                    'weight': rel['total_mentions'],
                    'confidence': rel['avg_confidence_score'],
                    'summary': rel['master_semantic_summary']
                })
            
            return {
                'nodes': list(nodes),
                'edges': edges
            }
    
    async def generate_oracle_response(self, question: str, context: Dict = None) -> str:
        """Generate oracle-style response based on stored relationships"""
        # Search for relevant relationships
        results = await self.search_relationships(question)
        
        if not results:
            return "No relevant relationships found for your query."
        
        # Format response
        response_parts = []
        
        # Group by company
        by_company = {}
        for r in results[:5]:  # Top 5 results
            company = r['company_domain']
            if company not in by_company:
                by_company[company] = []
            by_company[company].append(r)
        
        for company, relationships in by_company.items():
            response_parts.append(f"\n{company.upper()}:")
            for rel in relationships:
                summary = rel['master_semantic_summary'] or rel['semantic_summary']
                response_parts.append(f"• {summary}")
                if rel.get('semantic_impact'):
                    response_parts.append(f"  Impact: {rel['semantic_impact']}")
        
        return "\n".join(response_parts)

class AnalyticsDashboard:
    """Generate analytics dashboards and reports"""
    
    def __init__(self, analytics: RelationshipAnalytics):
        self.analytics = analytics
    
    async def generate_company_report(self, company_domain: str) -> Dict:
        """Generate comprehensive company report"""
        # Gather all data
        overview = await self.analytics.get_company_overview(company_domain)
        high_impact = await self.analytics.get_high_impact_relationships(company_domain)
        network = await self.analytics.get_relationship_network(company_domain)
        
        return {
            'report_date': datetime.now().isoformat(),
            'company': company_domain,
            'overview': overview,
            'high_impact_relationships': high_impact,
            'network_analysis': {
                'total_entities': len(network['nodes']) - 1,
                'total_relationships': len(network['edges']),
                'relationship_types': list(set(e['type'] for e in network['edges']))
            },
            'key_insights': self._extract_insights(overview, high_impact)
        }
    
    def _extract_insights(self, overview: Dict, high_impact: List[Dict]) -> List[str]:
        """Extract key insights from data"""
        insights = []
        
        # Relationship diversity
        if overview['summary'].get('relationship_types', 0) > 5:
            insights.append("Highly diversified relationship portfolio across multiple categories")
        
        # High-value relationships
        high_value = [r for r in high_impact if r.get('monetary_value', 0) > 100000000]
        if high_value:
            insights.append(f"Major financial commitments: {len(high_value)} relationships > $100M")
        
        # Positive momentum
        positive = [r for r in high_impact if r.get('semantic_impact') == 'positive']
        if len(positive) > len(high_impact) * 0.6:
            insights.append("Strong positive momentum in recent relationships")
        
        return insights

# Convenience functions

async def query_relationships(query: str, company: Optional[str] = None) -> List[Dict]:
    """Quick search for relationships"""
    from database_manager import DatabaseManager
    from pipeline_config import PipelineConfig
    
    config = PipelineConfig.from_env()
    db = DatabaseManager(config)
    analytics = RelationshipAnalytics(db)
    
    try:
        await db.initialize()
        results = await analytics.search_relationships(query, company)
        return results
    finally:
        await db.close()

def search(query: str, company: Optional[str] = None) -> List[Dict]:
    """Synchronous search wrapper"""
    return asyncio.run(query_relationships(query, company))

if __name__ == "__main__":
    # Example usage
    results = search("clinical trial", "modernatx.com")
    
    print(f"\nFound {len(results)} relationships")
    for r in results[:3]:
        print(f"\n{r['entity_name']} ({r['relationship_type']})")
        print(f"  {r['semantic_summary']}")
        print(f"  Confidence: {r['confidence_score']:.2f}")