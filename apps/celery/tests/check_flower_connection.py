#!/usr/bin/env python3
"""
Flower Diagnostic Tool - Identify and fix Flower connection issues
"""
import requests
import json
import time
from urllib.parse import urlparse
import subprocess
import os


def check_flower_connection():
    """Check if Flower is accessible and properly configured."""
    print("🌸 FLOWER DIAGNOSTIC TOOL")
    print("=" * 50)
    
    # Test different common Flower URLs
    test_urls = [
        "http://localhost:5555",
        "http://localhost:5555/api/workers",
        "http://admin:flower123@localhost:5555/api/workers",
        "http://admin:flower@localhost:5555/api/workers"
    ]
    
    for url in test_urls:
        print(f"\n🔗 Testing: {url}")
        try:
            response = requests.get(url, timeout=10)
            print(f"   Status: {response.status_code}")
            
            if response.status_code == 200:
                print("   ✅ SUCCESS! Flower is accessible")
                try:
                    data = response.json()
                    print(f"   📊 Workers found: {len(data) if isinstance(data, dict) else 'N/A'}")
                except:
                    print("   📄 HTML response (likely Flower UI)")
                return True
            elif response.status_code == 401:
                print("   🔐 Authentication required")
            elif response.status_code == 404:
                print("   ❌ Endpoint not found")
        except requests.exceptions.ConnectRefused:
            print("   ❌ Connection refused - Flower not running")
        except requests.exceptions.Timeout:
            print("   ⏰ Timeout - Flower not responding")
        except Exception as e:
            print(f"   ❌ Error: {e}")
    
    return False


def diagnose_docker_services():
    """Check Docker services status."""
    print("\n🐳 DOCKER SERVICES DIAGNOSTIC")
    print("=" * 50)
    
    services = [
        'discovery-celery-flower',
        'discovery-celery-worker', 
        'discovery-celery-beat',
        'discovery-rabbitmq',
        'discovery-redis'
    ]
    
    for service in services:
        try:
            result = subprocess.run(
                ['docker', 'ps', '--filter', f'name={service}', '--format', 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'],
                capture_output=True, text=True, timeout=10
            )
            
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                if len(lines) > 1:  # Header + data
                    print(f"✅ {service}:")
                    for line in lines[1:]:  # Skip header
                        print(f"   {line}")
                else:
                    print(f"❌ {service}: Not running")
            else:
                print(f"❌ {service}: Docker command failed")
                
        except subprocess.TimeoutExpired:
            print(f"⏰ {service}: Docker command timeout")
        except Exception as e:
            print(f"❌ {service}: Error - {e}")


def check_celery_broker_connection():
    """Test Celery broker connectivity."""
    print("\n🔗 CELERY BROKER CONNECTION")
    print("=" * 50)
    
    # Test RabbitMQ connection
    rabbitmq_urls = [
        "http://localhost:15672/api/overview",
        "http://guest:guest@localhost:15672/api/overview"
    ]
    
    for url in rabbitmq_urls:
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                print("✅ RabbitMQ Management accessible")
                data = response.json()
                print(f"   Message stats: {data.get('message_stats', {})}")
                break
        except Exception as e:
            print(f"❌ RabbitMQ test failed: {e}")
    
    # Test Redis connection
    try:
        import redis
        r = redis.Redis(host='localhost', port=6379, db=0)
        r.ping()
        print("✅ Redis connection successful")
    except Exception as e:
        print(f"❌ Redis connection failed: {e}")


def check_celery_workers():
    """Check if Celery workers are running and sending events."""
    print("\n👷 CELERY WORKERS DIAGNOSTIC")
    print("=" * 50)
    
    try:
        # Try to inspect workers using docker exec
        result = subprocess.run([
            'docker', 'exec', 'discovery-celery-worker',
            'celery', '-A', 'apps.celery.celery:celery', 'inspect', 'active'
        ], capture_output=True, text=True, timeout=15)
        
        if result.returncode == 0:
            print("✅ Celery workers responding")
            print(f"   Output: {result.stdout[:200]}...")
        else:
            print("❌ Celery workers not responding")
            print(f"   Error: {result.stderr}")
            
    except Exception as e:
        print(f"❌ Worker inspection failed: {e}")
    
    # Check if events are enabled
    try:
        result = subprocess.run([
            'docker', 'exec', 'discovery-celery-worker',
            'celery', '-A', 'apps.celery.celery:celery', 'events', '--dump'
        ], capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            print("✅ Celery events are working")
        else:
            print("❌ Celery events not enabled")
            print("   Run: docker exec discovery-celery-worker celery -A apps.celery.celery control enable_events")
            
    except Exception as e:
        print(f"❌ Events check failed: {e}")


def provide_flower_fixes():
    """Provide step-by-step fixes for common Flower issues."""
    print("\n🔧 FLOWER FIX RECOMMENDATIONS")
    print("=" * 50)
    
    fixes = [
        {
            "issue": "Flower Not Accessible",
            "commands": [
                "docker-compose logs celery-flower",
                "docker-compose restart celery-flower",
                "docker-compose ps celery-flower"
            ]
        },
        {
            "issue": "Authentication Problems", 
            "commands": [
                "curl -u admin:flower123 http://localhost:5555/api/workers",
                "export FLOWER_BASIC_AUTH=admin:flower123",
                "docker-compose up -d celery-flower"
            ]
        },
        {
            "issue": "No Workers Visible",
            "commands": [
                "docker exec discovery-celery-worker celery -A apps.celery.celery control enable_events",
                "docker-compose restart celery-worker",
                "docker-compose restart celery-flower"
            ]
        },
        {
            "issue": "Wrong Broker Configuration",
            "commands": [
                "# Update docker-compose.yml celery-flower environment:",
                "# - CELERY_BROKER_URL=amqp://guest:guest@rabbitmq:5672//",
                "docker-compose up -d celery-flower"
            ]
        }
    ]
    
    for fix in fixes:
        print(f"\n📋 {fix['issue']}:")
        for cmd in fix['commands']:
            if cmd.startswith('#'):
                print(f"   {cmd}")
            else:
                print(f"   $ {cmd}")


def quick_flower_fix():
    """Attempt to quickly fix Flower issues."""
    print("\n⚡ QUICK FLOWER FIX ATTEMPT")
    print("=" * 50)
    
    steps = [
        ("Stopping Flower", ['docker-compose', 'stop', 'celery-flower']),
        ("Enabling Worker Events", [
            'docker', 'exec', 'discovery-celery-worker',
            'celery', '-A', 'apps.celery.celery:celery', 'control', 'enable_events'
        ]),
        ("Starting Flower with Fixed Config", ['docker-compose', 'up', '-d', 'celery-flower']),
    ]
    
    for step_name, command in steps:
        print(f"\n🔄 {step_name}...")
        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                print(f"   ✅ Success")
            else:
                print(f"   ❌ Failed: {result.stderr}")
        except Exception as e:
            print(f"   ❌ Error: {e}")
    
    print("\n⏳ Waiting 10 seconds for services to stabilize...")
    time.sleep(10)
    
    print("\n🧪 Testing fixed Flower...")
    if check_flower_connection():
        print("\n🎉 FLOWER IS NOW WORKING!")
        print("   Access it at: http://localhost:5555")
        print("   Login: admin / flower123")
    else:
        print("\n😞 Quick fix didn't work. Try manual steps above.")


def generate_working_docker_compose():
    """Generate a working docker-compose snippet for Flower."""
    print("\n📝 WORKING FLOWER CONFIGURATION")
    print("=" * 50)
    
    config = """
# Add this to your docker-compose.yml services section:

  celery-flower:
    image: mher/flower:2.0.1
    container_name: discovery-celery-flower  
    restart: unless-stopped
    ports:
      - "5555:5555"
    environment:
      # CRITICAL: Use RabbitMQ broker URL (not Redis)
      - CELERY_BROKER_URL=amqp://guest:guest@rabbitmq:5672//
      - CELERY_RESULT_BACKEND=redis://redis:6379/0
      - FLOWER_BASIC_AUTH=admin:flower123
      - FLOWER_PERSISTENT=True
      - FLOWER_ENABLE_EVENTS=True
      - FLOWER_MAX_TASKS=10000
    depends_on:
      - rabbitmq
      - redis
      - celery-worker
    networks:
      - discovery-network
    command: >
      celery 
      --broker=amqp://guest:guest@rabbitmq:5672// 
      flower 
      --address=0.0.0.0 
      --port=5555 
      --basic_auth=admin:flower123
      --persistent=True
      --max_tasks=10000

  # Also update your celery-worker to enable events:
  celery-worker:
    # ... existing config ...
    environment:
      # ... existing vars ...
      - CELERY_SEND_EVENTS=True
      - CELERY_SEND_TASK_SENT_EVENT=True
    command: >
      celery -A apps.celery.celery:celery worker 
      --loglevel=info 
      --events  # CRITICAL: Enable events for Flower
      --queues=scheduled_queue,maintenance_queue
"""
    
    print(config)


def main():
    """Run complete Flower diagnostic."""
    print("🌸 DiscoveryBot Flower Diagnostic Tool")
    print("🔧 Identifying and fixing Celery Flower issues\n")
    
    # Run diagnostics
    flower_working = check_flower_connection()
    diagnose_docker_services()
    check_celery_broker_connection()
    check_celery_workers()
    
    if not flower_working:
        provide_flower_fixes()
        
        choice = input("\n❓ Would you like to attempt a quick fix? (y/n): ").lower()
        if choice == 'y':
            quick_flower_fix()
        
        print("\n📝 If issues persist, update your docker-compose.yml:")
        generate_working_docker_compose()
    
    print("\n✅ Diagnostic complete!")
    print("📊 For monitoring alternatives, see the custom dashboard provided.")


if __name__ == "__main__":
    main()