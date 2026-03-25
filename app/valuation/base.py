"""
Base valuation interface.
"""
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from datetime import datetime

from ..models import Auction, AuctionCategory, ValuationResult


class BaseValuator(ABC):
    """
    Abstract base class for valuation strategies.
    """
    
    @abstractmethod
    def valuate(
        self,
        auction: Auction,
        category: AuctionCategory,
        config: Dict[str, Any],
    ) -> Optional[ValuationResult]:
        """
        Estimate resale value and calculate max bid for an auction.
        
        Args:
            auction: Auction to valuate
            category: Category of the auction
            config: Configuration with costs, haircut, etc.
            
        Returns:
            ValuationResult or None if valuation not possible
        """
        pass
    
    def _calculate_roi_and_margin(
        self,
        resale_value: float,
        max_bid: float,
        total_costs: float,
    ) -> tuple:
        """
        Calculate ROI and margin.
        
        Returns:
            Tuple of (roi, margin)
        """
        total_investment = max_bid + total_costs
        if total_investment <= 0:
            return 0.0, 0.0
        
        margin = resale_value - total_investment
        roi = margin / total_investment
        
        return roi, margin
    
    def _get_category_config(
        self,
        category: AuctionCategory,
        config: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Get configuration for specific category."""
        cat_name = category.value
        return config.get('costs', {}).get(cat_name, config.get('costs', {}).get('altro', {}))


class ValuationError(Exception):
    """Exception raised when valuation fails."""
    pass