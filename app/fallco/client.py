"""
HTTP Client for Fallco Aste with rate limiting and retry logic.
"""
import time
import random
import logging
from typing import Optional, Dict, Any
from datetime import datetime, timedelta

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


logger = logging.getLogger(__name__)


class RateLimiter:
    """Simple rate limiter for API calls."""
    
    def __init__(self, max_calls: int, time_window: int):
        """
        Args:
            max_calls: Maximum number of calls allowed
            time_window: Time window in seconds
        """
        self.max_calls = max_calls
        self.time_window = time_window
        self._calls: list = []
    
    def acquire(self) -> None:
        """Wait until rate limit allows making a call."""
        now = time.time()
        
        # Remove old calls outside the window
        self._calls = [t for t in self._calls if now - t < self.time_window]
        
        if len(self._calls) >= self.max_calls:
            # Calculate wait time
            wait_time = self.time_window - (now - self._calls[0])
            if wait_time > 0:
                logger.debug(f"Rate limit reached, waiting {wait_time:.1f}s")
                time.sleep(wait_time)
                self._calls = []
        
        # Add current call timestamp
        self._calls.append(time.time())
    
    def reset(self) -> None:
        """Reset the rate limiter."""
        self._calls.clear()


class FallcoClient:
    """
    HTTP client for Fallco Aste with retry, timeout, and rate limiting.
    """
    
    def __init__(
        self,
        user_agent: str = "FallcoAsteBot/1.0",
        timeout: int = 30,
        max_retries: int = 3,
        rate_limit_per_minute: int = 30,
    ):
        """
        Initialize Fallco client.
        
        Args:
            user_agent: User agent string
            timeout: Request timeout in seconds
            max_retries: Maximum retry attempts
            rate_limit_per_minute: Rate limit calls per minute
        """
        self.user_agent = user_agent
        self.timeout = timeout
        self.max_retries = max_retries
        self.rate_limiter = RateLimiter(rate_limit_per_minute, 60)
        
        # Create session with retry strategy
        self.session = self._create_session()
        
        # Statistics
        self._stats = {
            'requests': 0,
            'errors': 0,
            'retries': 0,
        }
    
    def _create_session(self) -> requests.Session:
        """Create requests session with retry strategy."""
        session = requests.Session()
        
        retry_strategy = Retry(
            total=self.max_retries,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "HEAD"],
        )
        
        adapter = HTTPAdapter(
            max_retries=retry_strategy,
            pool_connections=10,
            pool_maxsize=10,
        )
        
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        return session
    
    def _get_headers(self) -> Dict[str, str]:
        """Get request headers."""
        return {
            'User-Agent': self.user_agent,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'it-IT,it;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
        }
    
    def get(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        add_jitter: bool = True,
    ) -> Optional[str]:
        """
        Make a GET request with rate limiting and retry.
        
        Args:
            url: URL to fetch
            params: Optional query parameters
            add_jitter: Add random delay to avoid detection
            
        Returns:
            Response text or None on failure
        """
        # Rate limit
        self.rate_limiter.acquire()
        
        # Add random jitter
        if add_jitter:
            time.sleep(random.uniform(0.1, 0.5))
        
        try:
            response = self.session.get(
                url,
                params=params,
                headers=self._get_headers(),
                timeout=self.timeout,
            )
            
            response.raise_for_status()
            self._stats['requests'] += 1
            
            logger.debug(f"GET {url} - Status: {response.status_code}")
            return response.text
        
        except requests.RequestException as e:
            self._stats['errors'] += 1
            logger.warning(f"Request failed for {url}: {type(e).__name__}: {e}")
            return None
        
        except Exception as e:
            self._stats['errors'] += 1
            logger.error(f"Unexpected error for {url}: {type(e).__name__}: {e}")
            return None
    
    def get_stats(self) -> Dict[str, Any]:
        """Get client statistics."""
        return {
            **self._stats,
            'session_cookies': len(self.session.cookies),
        }
    
    def reset_stats(self) -> None:
        """Reset statistics."""
        self._stats = {
            'requests': 0,
            'errors': 0,
            'retries': 0,
        }
    
    def close(self) -> None:
        """Close the session."""
        self.session.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()