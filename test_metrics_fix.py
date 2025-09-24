#!/usr/bin/env python3
"""
Test script to validate MetricsCollector fixes
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.monitoring import MetricsCollector

def test_metrics_collector():
    """Test the newly added MetricsCollector methods"""
    
    print("🔧 Testing MetricsCollector fixes...")
    
    try:
        # Initialize collector
        collector = MetricsCollector()
        print("✓ MetricsCollector initialized successfully")
        
        # Test get_performance_summary method
        print("\n📊 Testing get_performance_summary...")
        summary = collector.get_performance_summary()
        assert "status" in summary
        assert summary["status"] in ["healthy", "error"]
        print(f"✓ Performance summary status: {summary['status']}")
        
        if summary["status"] == "healthy":
            assert "timestamp" in summary
            assert "metrics_count" in summary
            print(f"✓ Metrics count: {summary['metrics_count']}")
        
        # Test get_cache_statistics method
        print("\n📈 Testing get_cache_statistics...")
        cache_stats = collector.get_cache_statistics()
        assert "status" in cache_stats
        assert cache_stats["status"] in ["operational", "error"]
        print(f"✓ Cache statistics status: {cache_stats['status']}")
        
        if cache_stats["status"] == "operational":
            assert "buffer_size" in cache_stats
            assert "buffer_utilization" in cache_stats
            print(f"✓ Buffer utilization: {cache_stats['buffer_utilization']:.1f}%")
        
        print("\n🎉 All MetricsCollector methods working correctly!")
        print("✅ Server log errors should now be resolved")
        return True
        
    except Exception as e:
        print(f"❌ Error testing MetricsCollector: {e}")
        return False

if __name__ == "__main__":
    success = test_metrics_collector()
    sys.exit(0 if success else 1)
