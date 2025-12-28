#!/usr/bin/env python3
"""
Advanced Traffic Generator for LLM Incident Commander
Generates diverse traffic patterns to trigger Datadog monitors and demonstrate observability.
"""
import argparse
import asyncio
import json
import random
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional
from collections import defaultdict

import httpx


class ScenarioType(Enum):
    """Traffic scenario types"""
    NORMAL = "normal"
    SLOW_QUERY = "slow_query"
    INVALID_INPUT = "invalid_input"
    HALLUCINATION_TRIGGER = "hallucination_trigger"
    COST_SPIKE = "cost_spike"
    BURST = "burst"


@dataclass
class TrafficStats:
    """Statistics for traffic generation"""
    total_requests: int = 0
    successful: int = 0
    failed: int = 0
    total_latency_ms: int = 0
    errors_by_type: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    requests_by_scenario: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate percentage"""
        if self.total_requests == 0:
            return 0.0
        return (self.successful / self.total_requests) * 100
    
    @property
    def avg_latency_ms(self) -> float:
        """Calculate average latency"""
        if self.successful == 0:
            return 0.0
        return self.total_latency_ms / self.successful


class TrafficGenerator:
    """
    Advanced traffic generator with multiple scenarios.
    Designed to trigger Datadog monitors and demonstrate incident management.
    """
    
    # Question templates for different scenarios
    NORMAL_QUESTIONS = [
        "What is the status of incident #{}?",
        "How do I troubleshoot error code {}?",
        "Explain the root cause of issue #{}",
        "What are the recommended steps for incident {}?",
        "Summarize the impact of problem #{}",
        "Provide mitigation steps for incident {}",
        "What is the current severity of issue #{}?",
        "List the affected services for incident {}",
    ]
    
    SLOW_QUESTIONS = [
        "Provide a comprehensive analysis of all possible failure scenarios in a distributed microservices architecture with eventual consistency, including network partitions, cascading failures, data inconsistencies, and recovery strategies for incident #{}",
        "Explain in extreme detail the entire debugging process for investigating memory leaks in production systems, covering profiling tools, heap analysis, garbage collection tuning, and long-term monitoring for issue #{}",
        "Generate a complete incident response playbook covering detection, triage, communication, escalation, mitigation, resolution, and post-mortem analysis for incident #{} with all possible edge cases",
        "Describe the full lifecycle of a distributed transaction across multiple databases, including two-phase commit, saga patterns, compensating transactions, and failure recovery for scenario #{}",
    ]
    
    INVALID_INPUTS = [
        "",  # Empty
        " " * 10,  # Whitespace only
        "a" * 10000,  # Extremely long
        "\x00\x01\x02",  # Binary data
        "🚀" * 1000,  # Many emojis
    ]
    
    HALLUCINATION_TRIGGERS = [
        # Uncertain/hedging responses
        "I'm not sure about this, but maybe you could tell me what you think might possibly be the answer to incident #{}?",
        "This is uncertain and I might be wrong, but could issue #{} be something you're not certain about?",
        
        # Contradictory prompts (should trigger judge)
        "Is incident #{} caused by high CPU or low CPU? Please confirm both are true.",
        "The database is both up and down at the same time for issue #{}. Explain why.",
        
        # Evasive question prompts
        "Just give me any generic response about incident #{}, doesn't matter what.",
        "Tell me something, anything really, about problem #{} without being specific.",
        
        # Factual impossibility (should trigger high judge score)
        "Explain how incident #{} was resolved in negative 5 seconds using quantum backwards time travel.",
        "Why did issue #{} happen on February 30th, 2024 at 25:99 PM?",
    ]
    
    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        rps: float = 2.0,
        duration_seconds: int = 300,
        scenario: Optional[ScenarioType] = None
    ):
        """
        Initialize traffic generator.
        
        Args:
            base_url: Base URL of the LLM service
            rps: Requests per second
            duration_seconds: How long to run (0 = infinite)
            scenario: Specific scenario to run, or None for mixed
        """
        self.base_url = base_url
        self.rps = rps
        self.duration_seconds = duration_seconds
        self.scenario = scenario
        self.stats = TrafficStats()
        self.running = False
        self.start_time = None
        
    def _get_question(self, scenario: ScenarioType, counter: int) -> str:
        """Get question based on scenario type"""
        if scenario == ScenarioType.NORMAL:
            template = random.choice(self.NORMAL_QUESTIONS)
            return template.format(counter)
        
        elif scenario == ScenarioType.SLOW_QUERY:
            template = random.choice(self.SLOW_QUESTIONS)
            return template.format(counter)
        
        elif scenario == ScenarioType.INVALID_INPUT:
            return random.choice(self.INVALID_INPUTS)
        
        elif scenario == ScenarioType.HALLUCINATION_TRIGGER:
            template = random.choice(self.HALLUCINATION_TRIGGERS)
            return template.format(counter)
        
        elif scenario == ScenarioType.BURST:
            # Burst uses normal questions but sent rapidly
            template = random.choice(self.NORMAL_QUESTIONS)
            return template.format(counter)
        
        return f"Default question {counter}"
    
    def _select_scenario(self) -> ScenarioType:
        """
        Select scenario based on weights.
        Distribution designed to trigger monitors periodically.
        """
        if self.scenario:
            return self.scenario
        
        # Weighted random selection
        # 70% normal, 15% slow, 10% hallucination, 5% invalid
        rand = random.random()
        
        if rand < 0.70:
            return ScenarioType.NORMAL
        elif rand < 0.85:
            return ScenarioType.SLOW_QUERY
        elif rand < 0.95:
            return ScenarioType.HALLUCINATION_TRIGGER
        else:
            return ScenarioType.INVALID_INPUT
    
    async def _send_request(
        self,
        client: httpx.AsyncClient,
        question: str,
        scenario: ScenarioType,
        counter: int
    ) -> None:
        """Send a single request and track statistics"""
        start = time.time()
        
        try:
            # Build payload with test_mode for specific scenarios
            payload = {"question": question}
            if scenario == ScenarioType.HALLUCINATION_TRIGGER:
                payload["test_mode"] = "hallucination"
            elif scenario == ScenarioType.COST_SPIKE:
                payload["test_mode"] = "cost"
            
            response = await client.post(
                f"{self.base_url}/ask",
                json=payload,
                timeout=60.0
            )
            
            latency_ms = int((time.time() - start) * 1000)
            
            self.stats.total_requests += 1
            self.stats.requests_by_scenario[scenario.value] += 1
            
            if response.status_code == 200:
                self.stats.successful += 1
                self.stats.total_latency_ms += latency_ms
                
                data = response.json()
                print(
                    f"✓ [{counter:04d}] {scenario.value:20s} | "
                    f"{latency_ms:5d}ms | "
                    f"tokens={data.get('tokens', {}).get('total', 0):4d} | "
                    f"cost=${data.get('cost_usd', 0):.6f}"
                )
            else:
                self.stats.failed += 1
                error_type = f"http_{response.status_code}"
                self.stats.errors_by_type[error_type] += 1
                
                print(
                    f"✗ [{counter:04d}] {scenario.value:20s} | "
                    f"{latency_ms:5d}ms | "
                    f"HTTP {response.status_code}"
                )
        
        except httpx.TimeoutException:
            self.stats.total_requests += 1
            self.stats.failed += 1
            self.stats.errors_by_type["timeout"] += 1
            print(f"✗ [{counter:04d}] {scenario.value:20s} | TIMEOUT")
        
        except Exception as e:
            self.stats.total_requests += 1
            self.stats.failed += 1
            self.stats.errors_by_type["exception"] += 1
            print(f"✗ [{counter:04d}] {scenario.value:20s} | ERROR: {str(e)[:50]}")
    
    def _print_stats(self) -> None:
        """Print current statistics"""
        if self.start_time:
            elapsed = time.time() - self.start_time
            current_rps = self.stats.total_requests / elapsed if elapsed > 0 else 0
        else:
            current_rps = 0
        
        print("\n" + "="*80)
        print(f"📊 TRAFFIC GENERATOR STATISTICS")
        print("="*80)
        print(f"Total Requests:    {self.stats.total_requests}")
        print(f"Successful:        {self.stats.successful} ({self.stats.success_rate:.1f}%)")
        print(f"Failed:            {self.stats.failed}")
        print(f"Avg Latency:       {self.stats.avg_latency_ms:.0f}ms")
        print(f"Current RPS:       {current_rps:.2f}")
        
        if self.stats.errors_by_type:
            print(f"\nErrors by Type:")
            for error_type, count in self.stats.errors_by_type.items():
                print(f"  - {error_type}: {count}")
        
        if self.stats.requests_by_scenario:
            print(f"\nRequests by Scenario:")
            for scenario, count in self.stats.requests_by_scenario.items():
                percentage = (count / self.stats.total_requests * 100) if self.stats.total_requests > 0 else 0
                print(f"  - {scenario}: {count} ({percentage:.1f}%)")
        
        print("="*80 + "\n")
    
    async def run(self) -> None:
        """Run the traffic generator"""
        self.running = True
        self.start_time = time.time()
        counter = 1
        
        print(f"\n🚀 Starting Traffic Generator")
        print(f"Target: {self.base_url}")
        print(f"RPS: {self.rps}")
        print(f"Duration: {self.duration_seconds}s" if self.duration_seconds > 0 else "Duration: infinite")
        print(f"Scenario: {self.scenario.value if self.scenario else 'mixed'}")
        print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*80 + "\n")
        
        delay_between_requests = 1.0 / self.rps
        
        async with httpx.AsyncClient() as client:
            try:
                while self.running:
                    # Check duration
                    if self.duration_seconds > 0:
                        elapsed = time.time() - self.start_time
                        if elapsed >= self.duration_seconds:
                            break
                    
                    # Select scenario and generate question
                    scenario = self._select_scenario()
                    question = self._get_question(scenario, counter)
                    
                    # Send request
                    await self._send_request(client, question, scenario, counter)
                    
                    counter += 1
                    
                    # Print stats every 20 requests
                    if counter % 20 == 0:
                        self._print_stats()
                    
                    # Rate limiting
                    await asyncio.sleep(delay_between_requests)
            
            except KeyboardInterrupt:
                print("\n\n⚠️  Interrupted by user")
            
            finally:
                self.running = False
                self._print_stats()
                print(f"✅ Traffic generation completed at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


async def test_connection(base_url: str) -> bool:
    """Test connection to the service"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{base_url}/health", timeout=10.0)
            if response.status_code == 200:
                data = response.json()
                print(f"✓ Service is healthy")
                print(f"  Service: {data.get('service')}")
                print(f"  Version: {data.get('version')}")
                print(f"  Vertex AI: {data.get('vertex_ai')}")
                return True
            else:
                print(f"✗ Service returned status {response.status_code}")
                return False
    except Exception as e:
        print(f"✗ Failed to connect: {e}")
        return False


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Advanced Traffic Generator for LLM Incident Commander"
    )
    parser.add_argument(
        "--url",
        default="http://localhost:8000",
        help="Base URL of the service (default: http://localhost:8000)"
    )
    parser.add_argument(
        "--rps",
        type=float,
        default=2.0,
        help="Requests per second (default: 2.0)"
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=300,
        help="Duration in seconds (default: 300, use 0 for infinite)"
    )
    parser.add_argument(
        "--scenario",
        choices=["normal", "slow_query", "invalid_input", "hallucination_trigger", "cost_spike", "burst"],
        help="Specific scenario to run (default: mixed)"
    )
    parser.add_argument(
        "--test-connection",
        action="store_true",
        help="Test connection to service and exit"
    )
    
    args = parser.parse_args()
    
    # Test connection if requested
    if args.test_connection:
        print(f"Testing connection to {args.url}...")
        success = asyncio.run(test_connection(args.url))
        sys.exit(0 if success else 1)
    
    # Convert scenario string to enum
    scenario = ScenarioType(args.scenario) if args.scenario else None
    
    # Create and run generator
    generator = TrafficGenerator(
        base_url=args.url,
        rps=args.rps,
        duration_seconds=args.duration,
        scenario=scenario
    )
    
    try:
        asyncio.run(generator.run())
    except KeyboardInterrupt:
        print("\n✅ Shutdown complete")
        sys.exit(0)


if __name__ == "__main__":
    main()
