"""
Proxy Manager: Manages proxy pool, sticky sessions, and TLS fingerprinting
"""

import json
import random
import time
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from pathlib import Path
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


@dataclass
class ProxyCredentials:
    """Proxy details"""
    address: str
    port: str
    username: Optional[str] = None
    password: Optional[str] = None
    
    def to_http_proxy(self) -> str:
        """Convert to HTTP proxy URL format"""
        if self.username and self.password:
            return f"http://{self.username}:{self.password}@{self.address}:{self.port}"
        return f"http://{self.address}:{self.port}"
    
    def to_https_proxy(self) -> str:
        """Convert to HTTPS proxy URL format"""
        if self.username and self.password:
            return f"https://{self.username}:{self.password}@{self.address}:{self.port}"
        return f"https://{self.address}:{self.port}"


@dataclass
class BrowserFingerprint:
    """Browser/device fingerprint for mimicry"""
    browser: str  # 'chrome', 'firefox', 'safari'
    platform: str  # 'Windows', 'Linux', 'macOS'
    user_agent: str
    accept_language: str
    accept_encoding: str = "gzip, deflate, br"
    
    def to_headers(self) -> Dict[str, str]:
        """Generate headers from fingerprint"""
        headers = {
            'User-Agent': self.user_agent,
            'Accept-Language': self.accept_language,
            'Accept-Encoding': self.accept_encoding,
        }
        
        # Add browser-specific headers
        if self.browser == 'chrome':
            headers.update({
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'same-site',
                'Upgrade-Insecure-Requests': '1',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
            })
        elif self.browser == 'firefox':
            headers.update({
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
                'DNT': '1',
            })
        
        return headers


@dataclass
class Session:
    """Sticky session for behavioral consistency"""
    session_id: str
    proxy: ProxyCredentials
    fingerprint: BrowserFingerprint
    created_at: datetime = None
    requests_made: int = 0
    last_used: datetime = None
    cookies: Dict = None
    referrer_chain: List[str] = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow()
        if self.cookies is None:
            self.cookies = {}
        if self.referrer_chain is None:
            self.referrer_chain = []
    
    def is_expired(self, max_requests: int = 30, max_age_minutes: int = 30) -> bool:
        """Check if session should be rotated"""
        if self.requests_made >= max_requests:
            return True
        
        age = datetime.utcnow() - self.created_at
        if age > timedelta(minutes=max_age_minutes):
            return True
        
        return False


class ProxyManager:
    """
    Manages proxy pool with:
    - Sticky sessions for behavioral consistency
    - Health monitoring
    - Intelligent selection and rotation
    - TLS fingerprint management
    """
    
    def __init__(self, proxies_file: str = "proxies.json", fingerprints_file: str = None):
        """
        Initialize proxy manager
        
        Args:
            proxies_file: Path to proxies.json with proxy credentials
            fingerprints_file: Optional path to custom fingerprints
        """
        self.proxies_file = Path(proxies_file)
        self.proxies: List[ProxyCredentials] = []
        self.proxy_health: Dict[str, dict] = {}  # Track health/success rates
        self.active_sessions: Dict[str, Session] = {}
        self.fingerprints = self._initialize_fingerprints(fingerprints_file)
        
        self._load_proxies()
    
    def _load_proxies(self):
        """Load proxies from JSON file"""
        if not self.proxies_file.exists():
            logger.warning(f"Proxies file not found: {self.proxies_file}")
            return
        
        try:
            with open(self.proxies_file, 'r') as f:
                data = json.load(f)
            
            for proxy_data in data:
                proxy = ProxyCredentials(
                    address=proxy_data.get('address'),
                    port=proxy_data.get('port'),
                    username=proxy_data.get('username'),
                    password=proxy_data.get('password'),
                )
                self.proxies.append(proxy)
                
                # Initialize health tracking
                proxy_key = proxy.to_http_proxy()
                self.proxy_health[proxy_key] = {
                    'success_count': 0,
                    'failure_count': 0,
                    'last_used': None,
                    'cooldown_until': None,
                }
            
            logger.info(f"Loaded {len(self.proxies)} proxies from {self.proxies_file}")
        except Exception as e:
            logger.error(f"Failed to load proxies: {e}")
    
    def _initialize_fingerprints(self, fingerprints_file: Optional[str] = None) -> List[BrowserFingerprint]:
        """Initialize browser fingerprints"""
        fingerprints = [
            # Chrome on Windows
            BrowserFingerprint(
                browser='chrome',
                platform='Windows',
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                accept_language='en-US,en;q=0.9',
            ),
            # Chrome on Mac
            BrowserFingerprint(
                browser='chrome',
                platform='macOS',
                user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                accept_language='en-US,en;q=0.9',
            ),
            # Firefox on Windows
            BrowserFingerprint(
                browser='firefox',
                platform='Windows',
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
                accept_language='en-US,en;q=0.5',
                accept_encoding='gzip, deflate',
            ),
            # Firefox on Linux
            BrowserFingerprint(
                browser='firefox',
                platform='Linux',
                user_agent='Mozilla/5.0 (X11; Linux x86_64; rv:121.0) Gecko/20100101 Firefox/121.0',
                accept_language='en-US,en;q=0.5',
                accept_encoding='gzip, deflate',
            ),
        ]
        
        # Load custom fingerprints if provided
        if fingerprints_file and Path(fingerprints_file).exists():
            try:
                with open(fingerprints_file, 'r') as f:
                    custom_fps = json.load(f)
                    for fp_data in custom_fps:
                        fingerprints.append(BrowserFingerprint(**fp_data))
            except Exception as e:
                logger.warning(f"Failed to load custom fingerprints: {e}")
        
        return fingerprints
    
    def create_session(self) -> Session:
        """Create a new sticky session with proxy and fingerprint"""
        proxy = self._select_proxy()
        fingerprint = random.choice(self.fingerprints)
        
        session_id = f"session_{int(time.time() * 1000)}"
        session = Session(
            session_id=session_id,
            proxy=proxy,
            fingerprint=fingerprint,
        )
        
        self.active_sessions[session_id] = session
        logger.info(f"Created session {session_id} with proxy {proxy.address}")
        
        return session
    
    def _select_proxy(self) -> ProxyCredentials:
        """
        Intelligently select proxy based on health and availability
        """
        if not self.proxies:
            raise ValueError("No proxies available")
        
        # Filter out proxies in cooldown
        available = []
        for proxy in self.proxies:
            proxy_key = proxy.to_http_proxy()
            health = self.proxy_health.get(proxy_key, {})
            
            cooldown_until = health.get('cooldown_until')
            if cooldown_until and datetime.utcnow() < cooldown_until:
                continue
            
            available.append(proxy)
        
        if not available:
            logger.warning("All proxies in cooldown, resetting")
            available = self.proxies
        
        # Weight by success rate
        proxy = self._weighted_proxy_selection(available)
        return proxy
    
    def _weighted_proxy_selection(self, proxies: List[ProxyCredentials]) -> ProxyCredentials:
        """Select proxy weighted by success rate"""
        weights = []
        
        for proxy in proxies:
            proxy_key = proxy.to_http_proxy()
            health = self.proxy_health.get(proxy_key, {})
            
            total = health.get('success_count', 0) + health.get('failure_count', 0)
            if total == 0:
                weight = 1.0
            else:
                success_rate = health['success_count'] / total
                weight = max(0.1, success_rate)  # Minimum weight of 0.1
            
            weights.append(weight)
        
        # Random selection weighted by health
        return random.choices(proxies, weights=weights, k=1)[0]
    
    def mark_request_success(self, session_id: str, site_domain: str = None):
        """Mark request as successful"""
        if session_id not in self.active_sessions:
            return
        
        session = self.active_sessions[session_id]
        proxy_key = session.proxy.to_http_proxy()
        
        session.requests_made += 1
        session.last_used = datetime.utcnow()
        
        if proxy_key in self.proxy_health:
            self.proxy_health[proxy_key]['success_count'] += 1
            self.proxy_health[proxy_key]['last_used'] = datetime.utcnow()
    
    def mark_request_failure(self, session_id: str, error_code: int = None):
        """Mark request as failed"""
        if session_id not in self.active_sessions:
            return
        
        session = self.active_sessions[session_id]
        proxy_key = session.proxy.to_http_proxy()
        
        if proxy_key in self.proxy_health:
            self.proxy_health[proxy_key]['failure_count'] += 1
            
            # Apply cooldown based on error
            if error_code == 429:  # Rate limited
                cooldown = timedelta(minutes=5)
                self.proxy_health[proxy_key]['cooldown_until'] = datetime.utcnow() + cooldown
                logger.warning(f"Proxy {session.proxy.address} rate limited, cooldown 5min")
            elif error_code == 403:  # Forbidden
                cooldown = timedelta(hours=1)
                self.proxy_health[proxy_key]['cooldown_until'] = datetime.utcnow() + cooldown
                logger.error(f"Proxy {session.proxy.address} forbidden, cooldown 1hr")
    
    def should_rotate_session(self, session_id: str) -> bool:
        """Check if session needs rotation"""
        if session_id not in self.active_sessions:
            return True
        
        session = self.active_sessions[session_id]
        return session.is_expired()
    
    def get_session(self, session_id: str) -> Optional[Session]:
        """Get session by ID"""
        return self.active_sessions.get(session_id)
    
    def close_session(self, session_id: str):
        """Close and remove session"""
        if session_id in self.active_sessions:
            del self.active_sessions[session_id]
            logger.info(f"Closed session {session_id}")
    
    def get_proxy_stats(self) -> Dict:
        """Get proxy pool statistics"""
        stats = {
            'total_proxies': len(self.proxies),
            'active_sessions': len(self.active_sessions),
            'proxy_health': {}
        }
        
        for proxy_key, health in self.proxy_health.items():
            total = health['success_count'] + health['failure_count']
            success_rate = health['success_count'] / total if total > 0 else 0
            
            stats['proxy_health'][proxy_key] = {
                'success_rate': success_rate,
                'total_requests': total,
                'failures': health['failure_count'],
            }
        
        return stats


class AdaptiveThrottler:
    """
    Adaptive request throttling based on:
    - Site-specific configuration
    - Response times
    - Error rates
    - Time of day
    """
    
    def __init__(self, config: Dict):
        """
        Initialize throttler
        
        Args:
            config: Global configuration with rate_limit settings
        """
        self.config = config
        self.request_times = {}  # Track request timing per domain
        self.last_request_time = {}  # Last request time per domain
    
    def calculate_delay(self, domain: str, site_config: Dict,
                       last_response_time: float = None) -> float:
        """
        Calculate adaptive delay
        
        Args:
            domain: Domain name
            site_config: Site-specific config with rate_limit settings
            last_response_time: Response time of last request (for adaptation)
        
        Returns:
            Delay in seconds
        """
        # Get base delay from config
        rate_limit = site_config.get('rate_limit', {})
        requests_per_minute = rate_limit.get('requests_per_minute', 30)
        base_delay = 60.0 / requests_per_minute
        
        # Apply adaptation based on response time
        if last_response_time:
            if last_response_time > 2.0:  # Slow response
                delay = base_delay * 2.0  # Double delay
                logger.debug(f"Server slow ({last_response_time:.1f}s), increasing delay to {delay:.1f}s")
            elif last_response_time > 0.5:  # Normal response
                delay = base_delay
            else:  # Fast response
                delay = base_delay * 0.8  # Slight speedup
        else:
            delay = base_delay
        
        # Add randomness (±10%)
        variance = delay * 0.1
        actual_delay = delay + random.uniform(-variance, variance)
        
        return max(0.5, actual_delay)  # Minimum 0.5 seconds
    
    def wait_if_needed(self, domain: str, site_config: Dict,
                      last_response_time: float = None):
        """
        Wait before making request if needed
        
        Args:
            domain: Domain name
            site_config: Site-specific configuration
            last_response_time: Last response time for adaptation
        """
        if domain not in self.last_request_time:
            self.last_request_time[domain] = datetime.utcnow()
            return
        
        delay = self.calculate_delay(domain, site_config, last_response_time)
        time_since_last = (datetime.utcnow() - self.last_request_time[domain]).total_seconds()
        
        if time_since_last < delay:
            wait_time = delay - time_since_last
            logger.debug(f"Throttling {domain}: waiting {wait_time:.2f}s")
            time.sleep(wait_time)
        
        self.last_request_time[domain] = datetime.utcnow()
