"""
Valuation for jewelry items (gold, silver, precious items).
"""
import re
import logging
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import requests

from ..models import Auction, AuctionCategory, ValuationResult
from .base import BaseValuator


logger = logging.getLogger(__name__)


class GoldSpotCache:
    """
    Cache for gold spot prices.
    """
    
    def __init__(self, cache_minutes: int = 10, fallback_price: float = 72.0):
        self.cache_minutes = cache_minutes
        self.fallback_price = fallback_price
        self._cached_price: Optional[float] = None
        self._cached_time: Optional[datetime] = None
    
    def get_price(self) -> float:
        """Get current gold price, using cache if available."""
        if self._cached_price and self._cached_time:
            age = datetime.now() - self._cached_time
            if age < timedelta(minutes=self.cache_minutes):
                return self._cached_price
        
        # Try to fetch new price
        price = self._fetch_gold_price()
        if price:
            self._cached_price = price
            self._cached_time = datetime.now()
            return price
        
        return self.fallback_price
    
    def _fetch_gold_price(self) -> Optional[float]:
        """
        Fetch gold price from public sources.
        Uses multiple fallbacks.
        """
        # Try to get from a public API
        # Note: Many gold APIs require registration, so we'll use a simple approach
        try:
            # Try a simple request to see if we can get any data
            # This is a placeholder - in production you'd use a real API
            response = requests.get(
                "https://api.metals.dev/v1/latest",
                params={"apiKey": "demo", "currency": "EUR", "unit": "g", "metal": "gold"},
                timeout=5,
            )
            if response.status_code == 200:
                data = response.json()
                price = data.get('metals', {}).get('gold', {}).get('price')
                if price:
                    logger.info(f"Fetched gold price: €{price}/g")
                    return float(price)
        except Exception as e:
            logger.debug(f"Could not fetch gold price: {e}")
        
        return None
    
    def invalidate(self) -> None:
        """Invalidate the cache."""
        self._cached_price = None
        self._cached_time = None


class JewelryValuator(BaseValuator):
    """
    Valuator for jewelry items (gold, silver, precious items).
    """
    
    def __init__(self, gold_cache: Optional[GoldSpotCache] = None):
        self.gold_cache = gold_cache or GoldSpotCache()
    
    def valuate(
        self,
        auction: Auction,
        category: AuctionCategory,
        config: Dict[str, Any],
    ) -> Optional[ValuationResult]:
        """
        Value a jewelry auction.
        
        Uses formula:
        - Extract grams and gold title (e.g., 750 = 75% gold)
        - Value = grams * (title/1000) * gold_price_per_gram
        - ResaleValue = Value * (1 - haircut)
        - MaxBid = ResaleValue * max_bid_percent - costs
        """
        cat_config = self._get_category_config(category, config)
        
        # Extract grams and title from auction
        grams, title = self._extract_grams_and_title(auction)
        
        if not grams or not title:
            logger.debug(f"Could not extract grams/title from {auction.url}")
            # Try fallback - if we can't determine, use conservative estimate
            return self._fallback_valuation(auction, category, config)
        
        # Get gold spot price
        gold_price = self.gold_cache.get_price()
        
        # Calculate pure gold value
        gold_content = grams * (title / 1000)
        raw_value = gold_content * gold_price
        
        # Apply haircut
        haircut = cat_config.get('haircut', 0.20)
        resale_value = raw_value * (1 - haircut)
        
        # Calculate costs
        costs = self._calculate_costs(category, cat_config)
        
        # Calculate max bid
        max_bid_percent = cat_config.get('max_bid_percent', 0.80)
        max_bid = (resale_value * max_bid_percent) - costs
        max_bid = max(0, max_bid)  # Don't allow negative
        
        # Calculate ROI and margin
        roi, margin = self._calculate_roi_and_margin(resale_value, max_bid, costs)
        
        # Determine confidence
        confidence = self._calculate_confidence(grams, title, auction)
        
        # Build notes
        notes = [
            f"Gold: {gold_price:.2f} €/g",
            f"Pure gold: {gold_content:.2f}g",
            f"Haircut: {haircut*100:.0f}%",
        ]
        
        # Check for risk factors
        risk_factors = []
        text = (auction.title or '') + (auction.description or '')
        if 'senza' in text.lower() or 'mancante' in text.lower():
            risk_factors.append("Item may be incomplete")
        
        return ValuationResult(
            category=category,
            resale_value=resale_value,
            max_bid=max_bid,
            total_costs=costs,
            roi=roi,
            margin=margin,
            confidence=confidence,
            notes=notes,
            risk_factors=risk_factors,
            raw_valuation={
                'grams': grams,
                'title': title,
                'gold_price': gold_price,
                'gold_content': gold_content,
                'raw_value': raw_value,
                'haircut': haircut,
            }
        )
    
    def _extract_grams_and_title(self, auction: Auction) -> tuple:
        """
        Extract grams and title from auction.
        
        Returns:
            Tuple of (grams, title) or (None, None)
        """
        text = (auction.title or '') + (auction.description or '') + (auction.raw_data.get('raw_text', '') or '')
        
        # Extract grams
        grams = None
        gram_patterns = [
            r'(\d+[.,]?\d*)\s*g[r]?\.?',
            r'gr\.?\s*(\d+[.,]?\d*)',
            r'grammi\s*(\d+[.,]?\d*)',
            r'peso\s*[:\s]*(\d+[.,]?\d*)',
        ]
        
        for pattern in gram_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                grams_str = match.group(1).replace(',', '.')
                try:
                    grams = float(grams_str)
                    break
                except ValueError:
                    pass
        
        # Extract title (gold purity)
        title = None
        title_patterns = [
            r'titolo\s*(\d{3})',
            r'(\d{3})\s*KT',
            r'(\d{3})\s*k',
            r'18\s*kt',
            r'24\s*kt',
            r'750\s*‰',
            r'585\s*‰',
        ]
        
        for pattern in title_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                if match.group(1).isdigit():
                    title = int(match.group(1))
                elif '18' in match.group(0):
                    title = 750
                elif '24' in match.group(0):
                    title = 1000
                break
        
        # If no explicit title, try to infer from context
        if not title:
            if '750' in text or '18k' in text.lower() or '18kt' in text.lower():
                title = 750
            elif '585' or '14k' in text.lower():
                title = 585
            elif '999' in text or '24k' in text.lower():
                title = 999
        
        return grams, title
    
    def _calculate_costs(self, category: AuctionCategory, cat_config: Dict[str, Any]) -> float:
        """Calculate total costs for jewelry."""
        commission = cat_config.get('commission_percent', 0.05)
        trasporto = cat_config.get('trasporto', 15)
        certificazione = cat_config.get('certificazione', 50)
        
        return trasporto + certificazione
    
    def _calculate_confidence(self, grams: Optional[float], title: Optional[int], auction: Auction) -> str:
        """Calculate confidence level for the valuation."""
        if not grams or not title:
            return 'low'
        
        # Check if we have specific details
        text = (auction.title or '') + (auction.description or '')
        
        if grams > 0 and title >= 500:
            return 'high'
        
        return 'medium'
    
    def _fallback_valuation(
        self,
        auction: Auction,
        category: AuctionCategory,
        config: Dict[str, Any],
    ) -> Optional[ValuationResult]:
        """
        Fallback valuation when we can't determine exact grams/title.
        
        Uses a conservative estimate based on base price.
        """
        cat_config = self._get_category_config(category, config)
        
        # Use base price as lower bound
        base_price = auction.base_price or auction.current_price or 0
        
        if base_price <= 0:
            return None
        
        # Conservative resale estimate
        resale_value = base_price * 1.1  # Assume some margin
        
        costs = self._calculate_costs(category, cat_config)
        
        max_bid_percent = cat_config.get('max_bid_percent', 0.80)
        max_bid = (resale_value * max_bid_percent) - costs
        max_bid = max(0, max_bid)
        
        roi, margin = self._calculate_roi_and_margin(resale_value, max_bid, costs)
        
        return ValuationResult(
            category=category,
            resale_value=resale_value,
            max_bid=max_bid,
            total_costs=costs,
            roi=roi,
            margin=margin,
            confidence='low',
            notes=["Fallback valuation - could not extract exact grams/title"],
            risk_factors=["Uncertain valuation - may need physical inspection"],
        )


class JewelryValuatorWithCache:
    """Wrapper to ensure gold cache is shared across valuations."""
    
    def __init__(self, cache: GoldSpotCache):
        self.valuator = JewelryValuator(cache)
    
    def valuate(self, auction: Auction, category: AuctionCategory, config: Dict[str, Any]):
        return self.valuator.valuate(auction, category, config)
    
    @property
    def gold_cache(self):
        return self.valuator.gold_cache