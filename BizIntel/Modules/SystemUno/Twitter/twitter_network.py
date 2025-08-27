"""
Twitter Network Analysis Module for SystemUno
Builds and analyzes social networks from Twitter interactions
"""

import logging
import networkx as nx
from typing import Dict, List, Tuple, Optional, Set
from collections import defaultdict
import numpy as np
from datetime import datetime, timedelta
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TwitterNetworkAnalyzer:
    """
    Analyzes Twitter networks for influence mapping and community detection
    """
    
    def __init__(self, db_config: Dict):
        """
        Initialize network analyzer
        
        Args:
            db_config: Database configuration
        """
        self.db_config = db_config
        self.graph = nx.DiGraph()
        
        # Algorithm parameters
        self.min_interactions = 3  # Minimum interactions to create edge
        self.centrality_algorithm = 'pagerank'
        self.community_algorithm = 'louvain'
    
    def build_network(self, 
                     interactions: List[Dict],
                     min_interactions: Optional[int] = None) -> nx.DiGraph:
        """
        Build network graph from Twitter interactions
        
        Args:
            interactions: List of interaction data (mentions, replies, retweets)
            min_interactions: Minimum interactions to create edge
            
        Returns:
            NetworkX directed graph
        """
        if min_interactions is None:
            min_interactions = self.min_interactions
        
        # Count interactions between users
        interaction_counts = defaultdict(lambda: defaultdict(int))
        
        for interaction in interactions:
            source = interaction.get('author_username')
            
            # Handle mentions
            if 'mentioned_users' in interaction:
                for mentioned in interaction['mentioned_users']:
                    target = mentioned.get('username')
                    if source and target and source != target:
                        interaction_counts[source][target] += 1
            
            # Handle replies
            if 'in_reply_to_user' in interaction:
                target = interaction['in_reply_to_user']
                if source and target and source != target:
                    interaction_counts[source][target] += 1
            
            # Handle retweets
            if 'referenced_tweets' in interaction:
                for ref in interaction['referenced_tweets']:
                    if ref.get('type') == 'retweeted':
                        target = ref.get('author_username')
                        if source and target and source != target:
                            interaction_counts[source][target] += 2  # Weight retweets higher
        
        # Build graph
        self.graph.clear()
        
        for source, targets in interaction_counts.items():
            for target, count in targets.items():
                if count >= min_interactions:
                    self.graph.add_edge(source, target, weight=count, interactions=count)
        
        # Add node attributes
        for node in self.graph.nodes():
            self.graph.nodes[node]['interactions_total'] = (
                sum(self.graph[node][target].get('weight', 0) 
                    for target in self.graph.neighbors(node)) +
                sum(self.graph[source][node].get('weight', 0) 
                    for source in self.graph.predecessors(node))
            )
        
        logger.info(f"Built network with {self.graph.number_of_nodes()} nodes and "
                   f"{self.graph.number_of_edges()} edges")
        
        return self.graph
    
    def calculate_centrality_metrics(self, 
                                    graph: Optional[nx.DiGraph] = None) -> Dict[str, Dict[str, float]]:
        """
        Calculate various centrality metrics for network nodes
        
        Args:
            graph: Network graph (uses self.graph if None)
            
        Returns:
            Dictionary of centrality metrics
        """
        if graph is None:
            graph = self.graph
        
        if graph.number_of_nodes() == 0:
            return {}
        
        metrics = {}
        
        try:
            # PageRank (Google's algorithm)
            metrics['pagerank'] = nx.pagerank(graph, weight='weight')
            
            # Degree centrality (normalized connections)
            metrics['in_degree'] = nx.in_degree_centrality(graph)
            metrics['out_degree'] = nx.out_degree_centrality(graph)
            
            # Betweenness centrality (information broker score)
            if graph.number_of_nodes() < 500:  # Expensive for large graphs
                metrics['betweenness'] = nx.betweenness_centrality(graph, weight='weight')
            
            # Eigenvector centrality (connected to important nodes)
            if graph.is_strongly_connected():
                metrics['eigenvector'] = nx.eigenvector_centrality(graph, weight='weight')
            
            # Closeness centrality (average distance to all nodes)
            if graph.is_strongly_connected():
                metrics['closeness'] = nx.closeness_centrality(graph, distance='weight')
            
        except Exception as e:
            logger.warning(f"Error calculating centrality metrics: {e}")
        
        return metrics
    
    def detect_communities(self, 
                          graph: Optional[nx.DiGraph] = None,
                          algorithm: Optional[str] = None) -> Dict[str, int]:
        """
        Detect communities in the network
        
        Args:
            graph: Network graph
            algorithm: Community detection algorithm
            
        Returns:
            Dictionary mapping nodes to community IDs
        """
        if graph is None:
            graph = self.graph
        
        if algorithm is None:
            algorithm = self.community_algorithm
        
        if graph.number_of_nodes() == 0:
            return {}
        
        # Convert to undirected for community detection
        undirected = graph.to_undirected()
        
        communities = {}
        
        try:
            if algorithm == 'louvain':
                import community as community_louvain
                communities = community_louvain.best_partition(undirected, weight='weight')
            elif algorithm == 'label_propagation':
                from networkx.algorithms import community
                comms = community.label_propagation_communities(undirected)
                for i, comm in enumerate(comms):
                    for node in comm:
                        communities[node] = i
            else:
                logger.warning(f"Unknown community algorithm: {algorithm}")
        except ImportError as e:
            logger.warning(f"Community detection library not available: {e}")
            # Fallback to connected components
            for i, component in enumerate(nx.weakly_connected_components(graph)):
                for node in component:
                    communities[node] = i
        except Exception as e:
            logger.error(f"Error detecting communities: {e}")
        
        return communities
    
    def identify_influencers(self, 
                            metrics: Dict[str, Dict[str, float]],
                            top_n: int = 10) -> List[Dict]:
        """
        Identify top influencers based on centrality metrics
        
        Args:
            metrics: Centrality metrics from calculate_centrality_metrics
            top_n: Number of top influencers to return
            
        Returns:
            List of influencer profiles with scores
        """
        if not metrics:
            return []
        
        # Calculate composite influence score
        influence_scores = {}
        
        # Weights for different metrics
        weights = {
            'pagerank': 0.4,
            'in_degree': 0.2,
            'out_degree': 0.1,
            'betweenness': 0.2,
            'eigenvector': 0.1
        }
        
        # Get all nodes
        all_nodes = set()
        for metric_dict in metrics.values():
            all_nodes.update(metric_dict.keys())
        
        for node in all_nodes:
            score = 0
            for metric_name, weight in weights.items():
                if metric_name in metrics and node in metrics[metric_name]:
                    # Normalize to 0-1 range
                    metric_values = list(metrics[metric_name].values())
                    if metric_values:
                        max_val = max(metric_values)
                        if max_val > 0:
                            normalized = metrics[metric_name][node] / max_val
                            score += normalized * weight
            
            influence_scores[node] = score * 100  # Scale to 0-100
        
        # Sort and get top N
        sorted_influencers = sorted(influence_scores.items(), 
                                   key=lambda x: x[1], 
                                   reverse=True)[:top_n]
        
        # Format results
        influencers = []
        for username, score in sorted_influencers:
            influencer = {
                'username': username,
                'influence_score': round(score, 2),
                'metrics': {}
            }
            
            # Add individual metrics
            for metric_name, metric_dict in metrics.items():
                if username in metric_dict:
                    influencer['metrics'][metric_name] = round(metric_dict[username], 4)
            
            # Add network position
            if username in self.graph:
                influencer['followers'] = self.graph.in_degree(username)
                influencer['following'] = self.graph.out_degree(username)
            
            influencers.append(influencer)
        
        return influencers
    
    def analyze_information_flow(self, 
                                source_node: str,
                                max_depth: int = 3) -> Dict:
        """
        Analyze how information flows from a source node
        
        Args:
            source_node: Starting node
            max_depth: Maximum depth to trace
            
        Returns:
            Information flow analysis
        """
        if source_node not in self.graph:
            return {'error': f'Node {source_node} not in network'}
        
        flow_analysis = {
            'source': source_node,
            'reach': {},
            'paths': [],
            'total_reach': 0
        }
        
        # BFS to trace information flow
        visited = {source_node: 0}
        queue = [(source_node, 0)]
        
        while queue:
            node, depth = queue.pop(0)
            
            if depth >= max_depth:
                continue
            
            for neighbor in self.graph.neighbors(node):
                if neighbor not in visited or visited[neighbor] > depth + 1:
                    visited[neighbor] = depth + 1
                    queue.append((neighbor, depth + 1))
                    
                    # Track reach at each level
                    level = f"level_{depth + 1}"
                    if level not in flow_analysis['reach']:
                        flow_analysis['reach'][level] = []
                    flow_analysis['reach'][level].append(neighbor)
        
        # Calculate total reach
        flow_analysis['total_reach'] = len(visited) - 1  # Exclude source
        
        # Find shortest paths to key nodes
        key_nodes = [n for n in visited if self.graph.in_degree(n) > 5][:5]
        for target in key_nodes:
            try:
                path = nx.shortest_path(self.graph, source_node, target)
                flow_analysis['paths'].append({
                    'target': target,
                    'path': path,
                    'length': len(path) - 1
                })
            except nx.NetworkXNoPath:
                pass
        
        return flow_analysis
    
    def find_bridges(self) -> List[Tuple[str, str]]:
        """
        Find bridge nodes that connect different communities
        
        Returns:
            List of bridge edges (source, target)
        """
        if self.graph.number_of_nodes() == 0:
            return []
        
        # Convert to undirected for bridge detection
        undirected = self.graph.to_undirected()
        
        try:
            bridges = list(nx.bridges(undirected))
            return bridges
        except:
            # If graph is not connected, find articulation points instead
            articulation_points = list(nx.articulation_points(undirected))
            
            # Find edges connected to articulation points
            bridge_edges = []
            for node in articulation_points:
                for neighbor in self.graph.neighbors(node):
                    bridge_edges.append((node, neighbor))
            
            return bridge_edges[:10]  # Limit to top 10
    
    def calculate_network_stats(self) -> Dict:
        """
        Calculate overall network statistics
        
        Returns:
            Network statistics dictionary
        """
        if self.graph.number_of_nodes() == 0:
            return {'nodes': 0, 'edges': 0}
        
        stats = {
            'nodes': self.graph.number_of_nodes(),
            'edges': self.graph.number_of_edges(),
            'density': nx.density(self.graph),
            'average_degree': sum(dict(self.graph.degree()).values()) / self.graph.number_of_nodes(),
            'connected_components': nx.number_weakly_connected_components(self.graph),
            'strongly_connected': nx.is_strongly_connected(self.graph)
        }
        
        # Diameter and average path length (expensive for large graphs)
        if self.graph.number_of_nodes() < 1000:
            if nx.is_strongly_connected(self.graph):
                stats['diameter'] = nx.diameter(self.graph)
                stats['avg_path_length'] = nx.average_shortest_path_length(self.graph)
            else:
                # Use largest strongly connected component
                largest_scc = max(nx.strongly_connected_components(self.graph), key=len)
                subgraph = self.graph.subgraph(largest_scc)
                if subgraph.number_of_nodes() > 1:
                    stats['diameter_scc'] = nx.diameter(subgraph)
                    stats['avg_path_length_scc'] = nx.average_shortest_path_length(subgraph)
        
        # Clustering coefficient
        stats['clustering_coefficient'] = nx.average_clustering(self.graph.to_undirected())
        
        return stats
    
    def export_for_visualization(self, 
                                 include_metrics: bool = True) -> Dict:
        """
        Export network data for visualization tools
        
        Args:
            include_metrics: Whether to include centrality metrics
            
        Returns:
            Network data in visualization format
        """
        if self.graph.number_of_nodes() == 0:
            return {'nodes': [], 'edges': []}
        
        # Calculate metrics if requested
        metrics = {}
        if include_metrics:
            metrics = self.calculate_centrality_metrics()
        
        # Export nodes
        nodes = []
        for node in self.graph.nodes():
            node_data = {
                'id': node,
                'label': node
            }
            
            # Add metrics
            if metrics:
                if 'pagerank' in metrics and node in metrics['pagerank']:
                    node_data['pagerank'] = metrics['pagerank'][node]
                if 'in_degree' in metrics and node in metrics['in_degree']:
                    node_data['in_degree'] = metrics['in_degree'][node]
            
            # Add attributes
            node_data.update(self.graph.nodes[node])
            nodes.append(node_data)
        
        # Export edges
        edges = []
        for source, target, data in self.graph.edges(data=True):
            edge_data = {
                'source': source,
                'target': target,
                'weight': data.get('weight', 1)
            }
            edges.append(edge_data)
        
        return {
            'nodes': nodes,
            'edges': edges,
            'stats': self.calculate_network_stats()
        }


# Example usage
if __name__ == "__main__":
    # Database config
    db_config = {
        'host': 'localhost',
        'database': 'smartreachbizintel',
        'user': 'srbiuser',
        'password': 'SRBI_dev_2025'
    }
    
    # Initialize analyzer
    analyzer = TwitterNetworkAnalyzer(db_config)
    
    # Sample interaction data
    interactions = [
        {
            'author_username': 'biotech_ceo',
            'mentioned_users': [{'username': 'fda_official'}, {'username': 'investor1'}],
            'in_reply_to_user': 'analyst1'
        },
        {
            'author_username': 'investor1',
            'mentioned_users': [{'username': 'biotech_ceo'}],
            'referenced_tweets': [{'type': 'retweeted', 'author_username': 'biotech_ceo'}]
        },
        {
            'author_username': 'analyst1',
            'mentioned_users': [{'username': 'biotech_ceo'}, {'username': 'investor1'}]
        },
        {
            'author_username': 'fda_official',
            'in_reply_to_user': 'biotech_ceo'
        },
        {
            'author_username': 'investor2',
            'referenced_tweets': [{'type': 'retweeted', 'author_username': 'analyst1'}]
        }
    ] * 3  # Multiply to meet min_interactions threshold
    
    print("Building Network...")
    print("="*60)
    
    # Build network
    graph = analyzer.build_network(interactions, min_interactions=2)
    
    # Calculate metrics
    print("\nCalculating Centrality Metrics...")
    metrics = analyzer.calculate_centrality_metrics()
    
    # Identify influencers
    print("\nTop Influencers:")
    print("-"*60)
    influencers = analyzer.identify_influencers(metrics, top_n=5)
    for i, influencer in enumerate(influencers, 1):
        print(f"{i}. @{influencer['username']}")
        print(f"   Influence Score: {influencer['influence_score']}")
        print(f"   PageRank: {influencer['metrics'].get('pagerank', 0):.4f}")
        print(f"   In-Degree: {influencer['metrics'].get('in_degree', 0):.4f}")
    
    # Detect communities
    print("\nCommunity Detection:")
    print("-"*60)
    communities = analyzer.detect_communities()
    community_counts = defaultdict(int)
    for node, comm_id in communities.items():
        community_counts[comm_id] += 1
    
    for comm_id, count in sorted(community_counts.items()):
        members = [n for n, c in communities.items() if c == comm_id]
        print(f"Community {comm_id}: {count} members - {', '.join(members[:3])}...")
    
    # Information flow
    print("\nInformation Flow Analysis:")
    print("-"*60)
    if graph.number_of_nodes() > 0:
        source = list(graph.nodes())[0]
        flow = analyzer.analyze_information_flow(source, max_depth=2)
        print(f"From @{source}:")
        print(f"  Total reach: {flow['total_reach']} users")
        for level, users in flow['reach'].items():
            print(f"  {level}: {len(users)} users")
    
    # Network statistics
    print("\nNetwork Statistics:")
    print("-"*60)
    stats = analyzer.calculate_network_stats()
    for key, value in stats.items():
        if isinstance(value, float):
            print(f"  {key}: {value:.4f}")
        else:
            print(f"  {key}: {value}")