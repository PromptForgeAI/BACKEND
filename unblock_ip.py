#!/usr/bin/env python3
"""
Quick script to unblock IP addresses from security middleware
"""

import sys
import os
sys.path.append(os.path.dirname(__file__))

from middleware.security import security_middleware

def unblock_localhost():
    """Unblock localhost IP addresses"""
    localhost_ips = ['127.0.0.1', 'localhost', '::1']
    
    for ip in localhost_ips:
        if ip in security_middleware.blocked_ips:
            security_middleware.blocked_ips.remove(ip)
            print(f"✅ Unblocked IP: {ip}")
        else:
            print(f"ℹ️  IP {ip} was not blocked")
    
    # Clear suspicious IP counts for localhost
    for ip in localhost_ips:
        if ip in security_middleware.suspicious_ips:
            del security_middleware.suspicious_ips[ip]
            print(f"✅ Cleared suspicious count for IP: {ip}")

if __name__ == "__main__":
    print("🔓 Unblocking localhost IPs...")
    unblock_localhost()
    print("✅ Done! You can now make requests to the API again.")
