import time
from collections import deque
from threading import Lock


class RequestStaggerer:
    """
    Manages request staggering with multiple strategies:
    - Fixed delay between requests
    - Exponential backoff on failures
    - Rate limiting (max requests per time window)
    - Jitter for distributed systems
    """

    def __init__(self,
                 fixed_delay=0.5,
                 max_requests_per_minute=60,
                 enable_exponential_backoff=True,
                 enable_jitter=False):
        """
        Initialize the request staggerer.

        Args:
            fixed_delay: Minimum seconds between requests
            max_requests_per_minute: Rate limit
            enable_exponential_backoff: Increase delay after failures
            enable_jitter: Add random variation to delays
        """
        self.fixed_delay = fixed_delay
        self.max_requests_per_minute = max_requests_per_minute
        self.enable_exponential_backoff = enable_exponential_backoff
        self.enable_jitter = enable_jitter

        # Track request timing
        self.last_request_time = 0
        self.request_times = deque(maxlen=max_requests_per_minute)
        self.lock = Lock()

        # Exponential backoff tracking
        self.consecutive_failures = 0
        self.backoff_multiplier = 1.0

    def wait_if_needed(self):
        """
        Block if necessary to maintain staggering constraints.
        Call this BEFORE making a request.
        """
        with self.lock:
            current_time = time.time()

            # 1. Fixed delay constraint
            time_since_last = current_time - self.last_request_time
            required_delay = self.fixed_delay * self.backoff_multiplier

            if self.enable_jitter:
                import random
                # Add ±20% random jitter
                jitter = random.uniform(-0.2, 0.2) * required_delay
                required_delay += jitter

            if time_since_last < required_delay:
                sleep_time = required_delay - time_since_last
                time.sleep(sleep_time)

            # 2. Rate limiting constraint
            self._enforce_rate_limit()

            # Update timing
            self.last_request_time = time.time()
            self.request_times.append(self.last_request_time)

    def _enforce_rate_limit(self):
        """Ensure we don't exceed max requests per minute."""
        if len(self.request_times) < self.max_requests_per_minute:
            return

        # Check if we're at the rate limit
        current_time = time.time()
        oldest_request = self.request_times[0]
        time_window = current_time - oldest_request

        if time_window < 60:  # Within 1 minute window
            # Need to wait until oldest request falls outside window
            wait_time = 60 - time_window + 0.1  # Small buffer
            print(f"Rate limit reached. Waiting {wait_time:.2f}s...")
            time.sleep(wait_time)

    def record_success(self):
        """Call after successful request to reset backoff."""
        if self.enable_exponential_backoff:
            self.consecutive_failures = 0
            self.backoff_multiplier = 1.0

    def record_failure(self):
        """Call after failed request to increase backoff."""
        if self.enable_exponential_backoff:
            self.consecutive_failures += 1
            # Double delay each failure, max 16x
            self.backoff_multiplier = min(2 ** self.consecutive_failures, 16)
            print(f"Request failed. Backoff multiplier: {self.backoff_multiplier}x")

    def get_stats(self):
        """Get current staggering statistics."""
        return {
            'total_requests': len(self.request_times),
            'requests_last_minute': len(self.request_times),
            'consecutive_failures': self.consecutive_failures,
            'current_backoff': self.backoff_multiplier,
            'time_since_last_request': time.time() - self.last_request_time
        }


class MultiAPIStaggerer:
    """
    Manages staggering for multiple different APIs with separate rate limits.
    """

    def __init__(self):
        self.staggerers = {}
        self.global_lock = Lock()

    def register_api(self, api_name, **kwargs):
        """
        Register an API with its own staggering configuration.

        Example:
            staggerer.register_api('iss_api', fixed_delay=0.3, max_requests_per_minute=120)
            staggerer.register_api('geo_api', fixed_delay=1.0, max_requests_per_minute=60)
        """
        with self.global_lock:
            self.staggerers[api_name] = RequestStaggerer(**kwargs)

    def wait_for_api(self, api_name):
        """Wait according to the specific API's constraints."""
        if api_name not in self.staggerers:
            raise ValueError(f"API '{api_name}' not registered. Call register_api() first.")

        self.staggerers[api_name].wait_if_needed()

    def record_result(self, api_name, success=True):
        """Record request result for the specific API."""
        if api_name in self.staggerers:
            if success:
                self.staggerers[api_name].record_success()
            else:
                self.staggerers[api_name].record_failure()

    def get_all_stats(self):
        """Get statistics for all registered APIs."""
        return {api: staggerer.get_stats()
                for api, staggerer in self.staggerers.items()}


# Example usage patterns:

def example_simple_stagger():
    """Example 1: Simple fixed delay between requests."""
    staggerer = RequestStaggerer(fixed_delay=1.0)

    for i in range(5):
        staggerer.wait_if_needed()
        print(f"Request {i + 1} at {time.time():.2f}")
        # Make your API call here
        staggerer.record_success()


def example_with_backoff():
    """Example 2: With exponential backoff on failures."""
    staggerer = RequestStaggerer(
        fixed_delay=0.5,
        enable_exponential_backoff=True
    )

    for i in range(5):
        staggerer.wait_if_needed()
        print(f"Request {i + 1}")

        # Simulate some failures
        if i in [1, 2]:
            print("  -> Failed!")
            staggerer.record_failure()
        else:
            print("  -> Success!")
            staggerer.record_success()


def example_multi_api():
    """Example 3: Different staggering for different APIs."""
    multi_staggerer = MultiAPIStaggerer()

    # Configure each API separately
    multi_staggerer.register_api('iss_api',
                                 fixed_delay=0.3,
                                 max_requests_per_minute=120)
    multi_staggerer.register_api('geo_api',
                                 fixed_delay=1.0,
                                 max_requests_per_minute=30)

    # Use them
    multi_staggerer.wait_for_api('iss_api')
    # Call ISS API
    multi_staggerer.record_result('iss_api', success=True)

    multi_staggerer.wait_for_api('geo_api')
    # Call Geo API
    multi_staggerer.record_result('geo_api', success=True)

    # Check stats
    print(multi_staggerer.get_all_stats())


if __name__ == "__main__":
    print("Example 1: Simple staggering")
    print("-" * 50)
    example_simple_stagger()

    print("\n\nExample 2: With exponential backoff")
    print("-" * 50)
    example_with_backoff()

    print("\n\nExample 3: Multi-API staggering")
    print("-" * 50)
    example_multi_api()