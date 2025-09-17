"""
Analytics Reporter for Entity Extraction Engine
Generate comprehensive analytics reports for pipeline performance.
"""

from EntityExtractionEngine.database_utils import get_db_connection


def generate_pipeline_analytics_report():
    """Generate comprehensive analytics report"""
    print("\n" + "="*80)
    print("📊 PIPELINE ANALYTICS REPORT")
    print("="*80)
    
    try:
        import psycopg2
        from kaggle_secrets import UserSecretsClient

        user_secrets = UserSecretsClient()
        with psycopg2.connect(
            host=user_secrets.get_secret("NEON_HOST"),
            database=user_secrets.get_secret("NEON_DATABASE"),
            user=user_secrets.get_secret("NEON_USER"),
            password=user_secrets.get_secret("NEON_PASSWORD"),
            port=5432,
            sslmode='require'
        ) as conn:
            cursor = conn.cursor()
            
            # Entity extraction statistics
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_entities,
                    COUNT(DISTINCT company_domain) as unique_companies,
                    COUNT(DISTINCT sec_filing_ref) as processed_filings,
                    AVG(confidence_score)::numeric(4,3) as avg_confidence,
                    AVG(quality_score)::numeric(4,3) as avg_quality
                FROM system_uno.sec_entities_raw
            """)
            
            entity_stats = cursor.fetchone()
            
            if entity_stats and entity_stats[0] > 0:
                print(f"\n📈 Entity Extraction Statistics:")
                print(f"   • Total entities extracted: {entity_stats[0]:,}")
                print(f"   • Unique companies: {entity_stats[1]:,}")
                print(f"   • Processed filings: {entity_stats[2]:,}")
                print(f"   • Average confidence: {entity_stats[3]}")
                print(f"   • Average quality: {entity_stats[4]}")
                
                # Entity type distribution
                cursor.execute("""
                    SELECT entity_type, COUNT(*) as count
                    FROM system_uno.sec_entities_raw
                    GROUP BY entity_type
                    ORDER BY count DESC
                    LIMIT 10
                """)
                
                entity_types = cursor.fetchall()
                print(f"\n📊 Top Entity Types:")
                for entity_type, count in entity_types:
                    print(f"   • {entity_type}: {count:,}")
                
                # Model performance
                cursor.execute("""
                    SELECT primary_model, COUNT(*) as count, AVG(confidence_score)::numeric(4,3) as avg_conf
                    FROM system_uno.sec_entities_raw
                    GROUP BY primary_model
                    ORDER BY count DESC
                """)
                
                model_performance = cursor.fetchall()
                print(f"\n🤖 Model Performance:")
                for model, count, avg_conf in model_performance:
                    print(f"   • {model}: {count:,} entities (avg confidence: {avg_conf})")
            
            else:
                print("\n⚠️ No entity data found in database")
            
            # Relationship statistics if available
            try:
                cursor.execute("""
                    SELECT 
                        COUNT(*) as total_relationships,
                        COUNT(DISTINCT bucket_id) as unique_buckets,
                        COUNT(DISTINCT company_domain) as companies_with_relationships
                    FROM system_uno.semantic_events se
                    JOIN system_uno.semantic_buckets sb ON se.bucket_id = sb.bucket_id
                """)
                
                rel_stats = cursor.fetchone()
                
                if rel_stats and rel_stats[0] > 0:
                    print(f"\n🔗 Relationship Analytics:")
                    print(f"   • Total relationships: {rel_stats[0]:,}")
                    print(f"   • Semantic buckets: {rel_stats[1]:,}")
                    print(f"   • Companies with relationships: {rel_stats[2]:,}")
                    
                    # Top relationship types
                    cursor.execute("""
                        SELECT relationship_type, COUNT(*) as count
                        FROM system_uno.semantic_buckets
                        GROUP BY relationship_type
                        ORDER BY count DESC
                        LIMIT 5
                    """)
                    
                    rel_types = cursor.fetchall()
                    print(f"\n🏷️ Top Relationship Types:")
                    for rel_type, count in rel_types:
                        print(f"   • {rel_type}: {count:,}")
                
                else:
                    print(f"\n📝 No relationship data found")
            
            except Exception as e:
                print(f"\n⚠️ Relationship analytics unavailable: {e}")
            
            cursor.close()
    
    except Exception as e:
        print(f"❌ Analytics report failed: {e}")