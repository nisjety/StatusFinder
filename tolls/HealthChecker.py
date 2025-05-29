#!/usr/bin/env python3
"""
DiscoveryBot System Health Checker
Run this script to verify all components are working correctly after deployment.
"""

import requests
import json
import time
import subprocess
from datetime import datetime, timedelta
from urllib.parse import urlparse


class HealthChecker:
    def __init__(self):
        self.results = []
        self.errors = []
        
    def log_result(self, test_name, success, message, details=None):
        """Log a test result."""
        status = "✅ PASS" if success else "❌ FAIL"
        self.results.append({
            "test": test_name,
            "success": success,
            "message": message,
            "details": details
        })
        print(f"{status} {test_name}: {message}")
        if details and not success:
            print(f"   Details: {details}")
        if not success:
            self.errors.append(f"{test_name}: {message}")

    def test_docker_services(self):
        """Test that all Docker services are running."""
        print("\n🐳 TESTING DOCKER SERVICES")
        print("=" * 50)
        
        required_services = [
            'discovery-redis',
            'discovery-mongodb', 
            'discovery-rabbitmq',
            'discovery-scrapyd',
            'discovery-scheduler',
            'discovery-celery-worker',
            'discovery-celery-beat',
            'discovery-celery-flower'
        ]
        
        try:
            result = subprocess.run(['docker', 'ps', '--format', 'json'], 
                                  capture_output=True, text=True, timeout=10)
            
            if result.returncode != 0:
                self.log_result("Docker Services", False, "Docker command failed", result.stderr)
                return
                
            running_containers = []
            for line in result.stdout.strip().split('\n'):
                if line.strip():
                    container = json.loads(line)
                    running_containers.append(container['Names'])
            
            for service in required_services:
                if service in running_containers:
                    self.log_result(f"Service {service}", True, "Running")
                else:
                    self.log_result(f"Service {service}", False, "Not running or not found")
                    
        except Exception as e:
            self.log_result("Docker Services", False, f"Error checking services: {e}")

    def test_redis_connection(self):
        """Test Redis connectivity."""
        print("\n🔴 TESTING REDIS")
        print("=" * 50)
        
        try:
            response = subprocess.run(['docker', 'exec', 'discovery-redis', 'redis-cli', 'ping'],
                                    capture_output=True, text=True, timeout=10)
            
            if response.returncode == 0 and 'PONG' in response.stdout:
                self.log_result("Redis Ping", True, "Redis responding correctly")
            else:
                self.log_result("Redis Ping", False, "Redis not responding", response.stderr)
                
        except Exception as e:
            self.log_result("Redis Connection", False, f"Error testing Redis: {e}")

    def test_mongodb_connection(self):
        """Test MongoDB connectivity."""
        print("\n🍃 TESTING MONGODB")
        print("=" * 50)
        
        try:
            response = subprocess.run([
                'docker', 'exec', 'discovery-mongodb',
                'mongosh', '--eval', 'db.adminCommand("ping")', '--quiet'
            ], capture_output=True, text=True, timeout=15)
            
            if response.returncode == 0:
                self.log_result("MongoDB Ping", True, "MongoDB responding correctly")
            else:
                self.log_result("MongoDB Ping", False, "MongoDB not responding", response.stderr)
                
        except Exception as e:
            self.log_result("MongoDB Connection", False, f"Error testing MongoDB: {e}")

    def test_rabbitmq_connection(self):
        """Test RabbitMQ connectivity."""
        print("\n🐰 TESTING RABBITMQ")
        print("=" * 50)
        
        # Test management API
        try:
            response = requests.get('http://localhost:15672/api/overview', 
                                  auth=('admin', 'guest'), timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                self.log_result("RabbitMQ Management API", True, 
                              f"Accessible - {data.get('management_version', 'Unknown version')}")
            else:
                self.log_result("RabbitMQ Management API", False, 
                              f"HTTP {response.status_code}", response.text[:100])
                              
        except Exception as e:
            self.log_result("RabbitMQ Management API", False, f"Connection failed: {e}")

    def test_scrapyd_connection(self):
        """Test Scrapyd connectivity."""
        print("\n🕷️ TESTING SCRAPYD")
        print("=" * 50)
        
        try:
            response = requests.get('http://localhost:6800/daemonstatus.json',
                                  auth=('admin', 'scrapyd'), timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                self.log_result("Scrapyd Daemon", True, 
                              f"Status: {data.get('status', 'unknown')}")
            else:
                self.log_result("Scrapyd Daemon", False, 
                              f"HTTP {response.status_code}", response.text[:100])
                              
        except Exception as e:
            self.log_result("Scrapyd Connection", False, f"Connection failed: {e}")

    def test_scheduler_api(self):
        """Test Scheduler API."""
        print("\n📅 TESTING SCHEDULER API")
        print("=" * 50)
        
        try:
            response = requests.get('http://localhost:8001/api/v1/health', timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                self.log_result("Scheduler Health", True, 
                              f"Service: {data.get('service', 'unknown')}")
            else:
                self.log_result("Scheduler Health", False, 
                              f"HTTP {response.status_code}", response.text[:100])
                              
        except Exception as e:
            self.log_result("Scheduler API", False, f"Connection failed: {e}")

    def test_flower_dashboard(self):
        """Test Flower dashboard."""
        print("\n🌸 TESTING FLOWER DASHBOARD")
        print("=" * 50)
        
        # Test Flower web interface
        try:
            response = requests.get('http://localhost:5555', 
                                  auth=('admin', 'flower123'), timeout=10)
            
            if response.status_code == 200:
                self.log_result("Flower Web Interface", True, "Dashboard accessible")
            else:
                self.log_result("Flower Web Interface", False, 
                              f"HTTP {response.status_code}")
        except Exception as e:
            self.log_result("Flower Web Interface", False, f"Connection failed: {e}")
            
        # Test Flower API
        try:
            response = requests.get('http://localhost:5555/api/workers',
                                  auth=('admin', 'flower123'), timeout=10)
            
            if response.status_code == 200:
                workers = response.json()
                worker_count = len(workers) if isinstance(workers, dict) else 0
                self.log_result("Flower API", True, f"Found {worker_count} worker(s)")
                
                if worker_count > 0:
                    for worker_name, worker_info in workers.items():
                        status = worker_info.get('status', 'unknown')
                        self.log_result(f"Worker {worker_name}", 
                                      status == 'Online', f"Status: {status}")
                else:
                    self.log_result("Celery Workers", False, "No workers found in Flower")
            else:
                self.log_result("Flower API", False, f"HTTP {response.status_code}")
                
        except Exception as e:
            self.log_result("Flower API", False, f"Error: {e}")

    def test_celery_workers(self):
        """Test Celery workers directly."""
        print("\n👷 TESTING CELERY WORKERS")
        print("=" * 50)
        
        try:
            # Test worker ping
            response = subprocess.run([
                'docker', 'exec', 'discovery-celery-worker',
                'celery', '-A', 'apps.celery.celery:celery', 'inspect', 'ping'
            ], capture_output=True, text=True, timeout=15)
            
            if response.returncode == 0:
                self.log_result("Celery Worker Ping", True, "Workers responding")
            else:
                self.log_result("Celery Worker Ping", False, "Workers not responding", 
                              response.stderr)
                
            # Test active tasks
            response = subprocess.run([
                'docker', 'exec', 'discovery-celery-worker',
                'celery', '-A', 'apps.celery.celery:celery', 'inspect', 'active'
            ], capture_output=True, text=True, timeout=15)
            
            if response.returncode == 0:
                self.log_result("Celery Active Tasks", True, "Command executed successfully")
            else:
                self.log_result("Celery Active Tasks", False, "Command failed", response.stderr)
                
        except Exception as e:
            self.log_result("Celery Workers", False, f"Error testing workers: {e}")

    def test_job_scheduling(self):
        """Test job scheduling functionality."""
        print("\n🎯 TESTING JOB SCHEDULING")
        print("=" * 50)
        
        # Test immediate job
        try:
            payload = {
                "user_id": "health-check",
                "spider": "quick",
                "start_urls": ["https://httpbin.org/status/200"],
                "depth": 0
            }
            
            response = requests.post('http://localhost:8001/api/v1/crawl',
                                   json=payload, timeout=15)
            
            if response.status_code in [200, 202]:
                self.log_result("Immediate Job Submission", True, "Job submitted successfully")
            else:
                self.log_result("Immediate Job Submission", False, 
                              f"HTTP {response.status_code}", response.text[:200])
                
        except Exception as e:
            self.log_result("Immediate Job Submission", False, f"Error: {e}")
            
        # Test scheduled job
        try:
            future_time = (datetime.utcnow() + timedelta(minutes=2)).isoformat() + "Z"
            payload = {
                "user_id": "health-check-scheduled",
                "spider": "quick", 
                "start_urls": ["https://httpbin.org/delay/1"],
                "schedule_at": future_time
            }
            
            response = requests.post('http://localhost:8001/api/v1/crawl',
                                   json=payload, timeout=15)
            
            if response.status_code in [200, 202]:
                data = response.json()
                if data.get('status') == 'scheduled':
                    self.log_result("Scheduled Job Submission", True, 
                                  f"Job scheduled for {future_time}")
                else:
                    self.log_result("Scheduled Job Submission", False, 
                                  "Unexpected response format", str(data))
            else:
                self.log_result("Scheduled Job Submission", False,
                              f"HTTP {response.status_code}", response.text[:200])
                
        except Exception as e:
            self.log_result("Scheduled Job Submission", False, f"Error: {e}")

    def run_all_tests(self):
        """Run all health checks."""
        print("🔍 DISCOVERYBOT SYSTEM HEALTH CHECK")
        print("=" * 60)
        print(f"Started at: {datetime.now().isoformat()}")
        
        # Run all tests
        self.test_docker_services()
        self.test_redis_connection()
        self.test_mongodb_connection()
        self.test_rabbitmq_connection()
        self.test_scrapyd_connection()
        self.test_scheduler_api()
        self.test_flower_dashboard()
        self.test_celery_workers()
        self.test_job_scheduling()
        
        # Summary
        print("\n" + "=" * 60)
        print("📊 HEALTH CHECK SUMMARY")
        print("=" * 60)
        
        total_tests = len(self.results)
        passed_tests = len([r for r in self.results if r['success']])
        failed_tests = total_tests - passed_tests
        
        print(f"Total Tests: {total_tests}")
        print(f"✅ Passed: {passed_tests}")
        print(f"❌ Failed: {failed_tests}")
        print(f"Success Rate: {(passed_tests/total_tests)*100:.1f}%")
        
        if self.errors:
            print(f"\n❌ FAILED TESTS ({len(self.errors)}):")
            for i, error in enumerate(self.errors, 1):
                print(f"   {i}. {error}")
        
        if failed_tests == 0:
            print("\n🎉 ALL TESTS PASSED! Your DiscoveryBot system is healthy!")
            print("\n📊 Access Points:")
            print("   • Flower Dashboard: http://localhost:5555 (admin/flower123)")
            print("   • RabbitMQ Management: http://localhost:15672 (admin/guest)")
            print("   • Scheduler API: http://localhost:8001/api/v1/health")
            print("   • Scrapyd Web UI: http://localhost:6800 (admin/scrapyd)")
        else:
            print(f"\n⚠️ {failed_tests} tests failed. Please check the errors above.")
            print("\n🔧 Quick fixes to try:")
            print("   1. docker-compose restart")
            print("   2. Check .env file configuration")
            print("   3. Verify all passwords are correct")
            print("   4. Check Docker service logs: docker-compose logs [service-name]")
        
        print(f"\nCompleted at: {datetime.now().isoformat()}")
        return failed_tests == 0


def main():
    """Main function."""
    checker = HealthChecker()
    success = checker.run_all_tests()
    exit(0 if success else 1)


if __name__ == "__main__":
    main()