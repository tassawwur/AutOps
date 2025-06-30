"""
Locust performance testing script for AutOps API.

Usage:
    locust -f benchmarks/locustfile.py --host=http://localhost:8000
    
Load test scenarios:
- Normal operations: locust -f benchmarks/locustfile.py --users 10 --spawn-rate 2
- Stress test: locust -f benchmarks/locustfile.py --users 100 --spawn-rate 10
- Peak load: locust -f benchmarks/locustfile.py --users 500 --spawn-rate 50
"""
from locust import HttpUser, task, between, events
import json
import random
import time


class AutOpsUser(HttpUser):
    """Simulated user for AutOps API testing."""
    
    wait_time = between(1, 5)  # Wait 1-5 seconds between requests
    
    def on_start(self):
        """Called when a simulated user starts."""
        self.user_id = f"U{random.randint(100000, 999999)}"
        self.channel_id = f"C{random.randint(100000, 999999)}"
        
        self.ci_queries = [
            "Is the latest build passing for checkout-service?",
            "What's the status of the deployment pipeline?",
            "Check CI status for main branch",
            "Show me the latest test results",
            "Is the build green?",
        ]
        
        self.metrics_queries = [
            "Payment-service is throwing 500s, what happened?",
            "Show me error rates for user-service in the last hour",
            "What's the CPU usage for api-service?",
            "Check memory utilization",
            "Any performance anomalies?",
        ]
        
        self.incident_queries = [
            "Are there any active incidents for auth-service?",
            "Show open incidents",
            "What caused the last outage?",
            "Create incident for slow API responses",
            "Update incident status",
        ]

    @task(5)
    def health_check(self):
        """Test health endpoint - most frequent."""
        with self.client.get("/health", catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Health check failed: {response.status_code}")

    @task(3)
    def readiness_check(self):
        """Test readiness endpoint."""
        with self.client.get("/ready", catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Readiness check failed: {response.status_code}")

    @task(2)
    def metrics_endpoint(self):
        """Test metrics endpoint."""
        with self.client.get("/metrics", catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Metrics endpoint failed: {response.status_code}")

    @task(1)
    def root_endpoint(self):
        """Test root endpoint."""
        with self.client.get("/", catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Root endpoint failed: {response.status_code}")

    @task(10)
    def slack_ci_queries(self):
        """Test CI-related queries through Slack webhook."""
        event_data = {
            "type": "event_callback",
            "token": "verification-token",
            "event": {
                "type": "app_mention",
                "text": f"<@UBOT123> {random.choice(self.ci_queries)}",
                "channel": self.channel_id,
                "user": self.user_id,
                "ts": f"{time.time():.6f}"
            }
        }
        
        with self.client.post(
            "/webhooks/slack",
            json=event_data,
            headers={"Content-Type": "application/json"},
            catch_response=True
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Slack CI query failed: {response.status_code}")

    @task(8)
    def slack_metrics_queries(self):
        """Test metrics queries through Slack webhook."""
        event_data = {
            "type": "event_callback",
            "token": "verification-token",
            "event": {
                "type": "message",
                "text": random.choice(self.metrics_queries),
                "channel": self.channel_id,
                "user": self.user_id,
                "ts": f"{time.time():.6f}"
            }
        }
        
        with self.client.post(
            "/webhooks/slack",
            json=event_data,
            headers={"Content-Type": "application/json"},
            catch_response=True
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Slack metrics query failed: {response.status_code}")

    @task(6)
    def slack_incident_queries(self):
        """Test incident management queries."""
        event_data = {
            "type": "event_callback",
            "token": "verification-token",
            "event": {
                "type": "message",
                "text": random.choice(self.incident_queries),
                "channel": self.channel_id,
                "user": self.user_id,
                "ts": f"{time.time():.6f}"
            }
        }
        
        with self.client.post(
            "/webhooks/slack",
            json=event_data,
            headers={"Content-Type": "application/json"},
            catch_response=True
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Slack incident query failed: {response.status_code}")

    @task(3)
    def slack_approval_interactions(self):
        """Test approval workflow interactions."""
        interaction_payload = {
            "payload": json.dumps({
                "type": "interactive_message",
                "actions": [
                    {
                        "name": random.choice(["approve", "reject"]),
                        "type": "button",
                        "value": f"deploy_prod_{random.randint(10000, 99999)}"
                    }
                ],
                "callback_id": "approval_request",
                "user": {"id": self.user_id, "name": "test_user"},
                "channel": {"id": self.channel_id},
                "message_ts": f"{time.time():.6f}"
            })
        }
        
        with self.client.post(
            "/webhooks/slack/interactive",
            data=interaction_payload,
            catch_response=True
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Approval interaction failed: {response.status_code}")

    @task(2)
    def concurrent_requests(self):
        """Test handling of rapid concurrent requests."""
        # Send multiple rapid requests to test concurrency
        queries = ["Quick check", "Fast status", "Rapid query"]
        
        for i, query in enumerate(queries):
            event_data = {
                "type": "event_callback",
                "token": "verification-token",
                "event": {
                    "type": "message",
                    "text": f"{query} #{i}",
                    "channel": self.channel_id,
                    "user": self.user_id,
                    "ts": f"{time.time():.6f}"
                }
            }
            
            with self.client.post(
                "/webhooks/slack",
                json=event_data,
                headers={"Content-Type": "application/json"},
                catch_response=True
            ) as response:
                if response.status_code == 200:
                    response.success()
                else:
                    response.failure(f"Concurrent request {i} failed: {response.status_code}")


class StressTestUser(HttpUser):
    """High-load stress test user for performance limits."""
    
    wait_time = between(0.1, 0.5)  # Very fast requests
    weight = 1  # Lower weight for stress testing
    
    def on_start(self):
        """Setup for stress test user."""
        self.user_id = f"STRESS{random.randint(1000, 9999)}"
        self.channel_id = f"CSTRESS{random.randint(1000, 9999)}"
    
    @task(20)
    def rapid_fire_requests(self):
        """Send rapid-fire requests to test system limits."""
        event_data = {
            "type": "event_callback",
            "token": "verification-token",
            "event": {
                "type": "message",
                "text": "stress test query",
                "channel": self.channel_id,
                "user": self.user_id,
                "ts": f"{time.time():.6f}"
            }
        }
        
        with self.client.post(
            "/webhooks/slack",
            json=event_data,
            headers={"Content-Type": "application/json"},
            catch_response=True
        ) as response:
            if response.status_code == 200:
                response.success()
            elif response.status_code == 429:  # Rate limited
                response.success()  # This is expected under stress
            else:
                response.failure(f"Stress test failed: {response.status_code}")

    @task(10)
    def health_stress(self):
        """Stress test health endpoint."""
        with self.client.get("/health", catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Health stress test failed: {response.status_code}")


class BenchmarkUser(HttpUser):
    """User for performance benchmarking with SLA assertions."""
    
    wait_time = between(1, 3)
    
    @task
    def benchmark_health_check(self):
        """Benchmark health check response times."""
        start_time = time.time()
        response = self.client.get("/health")
        end_time = time.time()
        
        response_time = (end_time - start_time) * 1000  # Convert to ms
        
        # SLA: Health check should respond within 100ms
        if response_time > 100:
            print(f"SLA VIOLATION: Health check took {response_time:.2f}ms (SLA: <100ms)")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"

    @task
    def benchmark_slack_webhook(self):
        """Benchmark Slack webhook response times."""
        event_data = {
            "type": "event_callback",
            "token": "verification-token",
            "event": {
                "type": "message",
                "text": "benchmark query",
                "channel": "C1234567890",
                "user": "U1234567890",
                "ts": f"{time.time():.6f}"
            }
        }
        
        start_time = time.time()
        response = self.client.post(
            "/webhooks/slack",
            json=event_data,
            headers={"Content-Type": "application/json"}
        )
        end_time = time.time()
        
        response_time = (end_time - start_time) * 1000  # Convert to ms
        
        # SLA: Slack webhook should respond within 3 seconds
        if response_time > 3000:
            print(f"SLA VIOLATION: Slack webhook took {response_time:.2f}ms (SLA: <3000ms)")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"


# Event listeners for test reporting
@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Setup before test starts."""
    print("🚀 Starting AutOps performance test...")
    print(f"Target host: {environment.host}")
    print(f"User classes: {[cls.__name__ for cls in environment.user_classes]}")


@events.test_stop.add_listener  
def on_test_stop(environment, **kwargs):
    """Generate test report after test stops."""
    print("\n" + "="*60)
    print("📊 AutOps Performance Test Results")
    print("="*60)
    
    stats = environment.stats.total
    print(f"Total requests: {stats.num_requests}")
    print(f"Total failures: {stats.num_failures}")
    print(f"Failure rate: {(stats.num_failures/stats.num_requests*100):.2f}%" if stats.num_requests > 0 else "0%")
    print(f"Average response time: {stats.avg_response_time:.2f}ms")
    print(f"Median response time: {stats.median_response_time:.2f}ms")
    print(f"95th percentile: {stats.get_response_time_percentile(0.95):.2f}ms")
    print(f"99th percentile: {stats.get_response_time_percentile(0.99):.2f}ms")
    print(f"Max response time: {stats.max_response_time:.2f}ms")
    print(f"Requests per second: {stats.total_rps:.2f}")
    
    # SLA checks
    print("\n📋 SLA Compliance:")
    p95 = stats.get_response_time_percentile(0.95)
    if p95 <= 3000:
        print(f"✅ 95th percentile response time: {p95:.2f}ms (SLA: <3000ms)")
    else:
        print(f"❌ 95th percentile response time: {p95:.2f}ms (SLA: <3000ms)")
    
    failure_rate = (stats.num_failures/stats.num_requests*100) if stats.num_requests > 0 else 0
    if failure_rate <= 1:
        print(f"✅ Failure rate: {failure_rate:.2f}% (SLA: <1%)")
    else:
        print(f"❌ Failure rate: {failure_rate:.2f}% (SLA: <1%)")
    
    print("="*60) 