"""
Data source for fetching auctions from Fallco.
"""
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from urllib.parse import urljoin, urlparse, parse_qs

from .client import FallcoClient
from .parser import FallcoParser


logger = logging.getLogger(__name__)


class FallcoSource:
    """
    Source for fetching auction data from Fallco Aste.
    """
    
    def __init__(
        self,
        client: FallcoClient,
        parser: FallcoParser,
        max_pages: int = 5,
    ):
        """
        Initialize Fallco source.
        
        Args:
            client: HTTP client
            parser: HTML parser
            max_pages: Maximum pages to fetch per source
        """
        self.client = client
        self.parser = parser
        self.max_pages = max_pages
    
    def fetch_auctions(
        self,
        source_url: str,
        horizon_minutes: int = 60,
    ) -> List[Dict[str, Any]]:
        """
        Fetch auctions from a source URL.
        
        Args:
            source_url: URL of the source to fetch
            horizon_minutes: Only return auctions expiring within this time
            
        Returns:
            List of auction data dictionaries
        """
        all_auctions = []
        
        # First try the main page
        html = self.client.get(source_url)
        if html:
            auctions = self.parser.parse_listing_page(html, source_url)
            logger.info(f"Found {len(auctions)} auctions on first page of {source_url}")
            all_auctions.extend(auctions)
        
        # Try pagination
        for page in range(2, self.max_pages + 1):
            page_url = self._get_pagination_url(source_url, page)
            if not page_url:
                break
            
            html = self.client.get(page_url)
            if not html:
                break
            
            auctions = self.parser.parse_listing_page(html, page_url)
            if not auctions:
                break
                
            logger.info(f"Found {len(auctions)} auctions on page {page} of {source_url}")
            all_auctions.extend(auctions)
        
        # Filter by horizon
        filtered = self._filter_by_horizon(all_auctions, horizon_minutes)
        
        return filtered
    
    def _get_pagination_url(self, base_url: str, page: int) -> Optional[str]:
        """Get URL for pagination."""
        parsed = urlparse(base_url)
        query = parse_qs(parsed.query)
        
        # Check if page param already exists
        if 'page' in query:
            query['page'] = [str(page)]
        else:
            # Try adding page parameter
            if '?' in base_url:
                return f"{base_url}&page={page}"
            else:
                return f"{base_url}?page={page}"
        
        # Rebuild URL
        from urllib.parse import urlencode
        new_query = urlencode(query, doseq=True)
        return f"{parsed.scheme}://{parsed.netloc}{parsed.path}?{new_query}"
    
    def _filter_by_horizon(
        self,
        auctions: List[Dict[str, Any]],
        horizon_minutes: int,
    ) -> List[Dict[str, Any]]:
        """Filter auctions by expiration horizon."""
        filtered = []
        now = datetime.now()
        horizon = timedelta(minutes=horizon_minutes)
        
        for auction in auctions:
            end_dt = auction.get('end_datetime')
            if end_dt:
                if isinstance(end_dt, str):
                    try:
                        from dateutil import parser as date_parser
                        end_dt = date_parser.parse(end_dt)
                    except Exception:
                        continue
                
                if end_dt <= now + horizon:
                    filtered.append(auction)
            else:
                # If no end datetime, include it (might be able to parse later)
                filtered.append(auction)
        
        return filtered
    
    def fetch_auction_detail(self, url: str) -> Optional[Dict[str, Any]]:
        """
        Fetch detailed information for a single auction.
        
        Args:
            url: URL of the auction detail page
            
        Returns:
            Auction data dictionary with more details
        """
        html = self.client.get(url)
        if not html:
            return None
        
        return self.parser.parse_detail_page(html, url)
    
    def get_auction_keyword_data(self, text: str) -> Dict[str, Any]:
        """
        Extract keyword data from auction text.
        
        Args:
            text: Text content from auction
            
        Returns:
            Dictionary with extracted data
        """
        return self.parser.extract_keyword_data(text)


class FallcoSources:
    """
    Manager for all Fallco data sources.
    """
    
    DEFAULT_SOURCES = [
        {
            'name': 'ricerca',
            'url': 'https://www.fallcoaste.it/ricerca.html',
            'enabled': True,
        },
        {
            'name': 'autovetture',
            'url': 'https://www.fallcoaste.it/categoria/autovetture-594.html',
            'enabled': True,
        },
        {
            'name': 'autoveicoli',
            'url': 'https://www.fallcoaste.it/categoria/autoveicoli-e-cicli-592.html',
            'enabled': True,
        },
        {
            'name': 'preziosi',
            'url': 'https://www.fallcoaste.it/categoria/preziosi-635.html',
            'enabled': True,
        },
        {
            'name': 'orologeria',
            'url': 'https://www.fallcoaste.it/categoria/arte-oreficeria-orologeria-antiquariato-633.html',
            'enabled': True,
        },
    ]
    
    def __init__(self, config: Dict[str, Any], client: FallcoClient, parser: FallcoParser):
        """
        Initialize sources manager.
        
        Args:
            config: Configuration dictionary
            client: HTTP client
            parser: HTML parser
        """
        self.config = config
        self.client = client
        self.parser = parser
        self.sources = self._load_sources(config)
    
    def _load_sources(self, config: Dict[str, Any]) -> List[FallcoSource]:
        """Load enabled sources from config."""
        source_configs = config.get('sources', self.DEFAULT_SOURCES)
        max_pages = config.get('scanner', {}).get('max_pages_per_source', 5)
        
        sources = []
        for sc in source_configs:
            if sc.get('enabled', True):
                sources.append(FallcoSource(
                    client=self.client,
                    parser=self.parser,
                    max_pages=max_pages,
                ))
        
        return sources
    
    def get_source_urls(self) -> List[Dict[str, str]]:
        """Get list of source URLs and names."""
        source_configs = self.config.get('sources', self.DEFAULT_SOURCES)
        return [
            {'name': sc['name'], 'url': sc['url']}
            for sc in source_configs if sc.get('enabled', True)
        ]
    
    def fetch_all(
        self,
        horizon_minutes: int = 60,
    ) -> List[Dict[str, Any]]:
        """
        Fetch auctions from all enabled sources.
        
        Args:
            horizon_minutes: Only return auctions expiring within this time
            
        Returns:
            List of all auction data
        """
        all_auctions = []
        source_urls = self.get_source_urls()
        
        for source in source_urls:
            logger.info(f"Fetching from source: {source['name']}")
            try:
                # Create a fresh source instance for each source
                src = FallcoSource(
                    client=self.client,
                    parser=self.parser,
                    max_pages=self.config.get('scanner', {}).get('max_pages_per_source', 5),
                )
                auctions = src.fetch_auctions(source['url'], horizon_minutes)
                logger.info(f"Found {len(auctions)} auctions from {source['name']}")
                all_auctions.extend(auctions)
            except Exception as e:
                logger.error(f"Error fetching from {source['name']}: {e}")
        
        return all_auctions