"""
Valuation for watches.
"""
import re
import logging
from typing import Optional, Dict, Any

from ..models import Auction, AuctionCategory, ValuationResult
from .base import BaseValuator


logger = logging.getLogger(__name__)


class WatchValuator(BaseValuator):
    """
    Valuator for watches.
    
    Uses brand tier system and condition factors to estimate resale value.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        
        # Brand tiers from config
        self.brand_tiers = self.config.get('watch_brands', {
            'luxury': ['Rolex', 'Patek Philippe', 'Audemars Piguet'],
            'high': ['Cartier', 'Tag Heuer', 'Longines', 'Omega'],
            'mid': ['Seiko', 'Citizen', 'Tissot'],
            'low': ['Generic', 'Fashion'],
        })
        
        # Base values by tier
        self.base_values = self.config.get('watch_values', {
            'luxury': 5000,
            'high': 1500,
            'mid': 300,
            'low': 100,
        })
    
    def valuate(
        self,
        auction: Auction,
        category: AuctionCategory,
        config: Dict[str, Any],
    ) -> Optional[ValuationResult]:
        """
        Value a watch auction.
        
        Formula:
        - Identify brand and tier
        - Apply condition factors (box, papers, working)
        - ResaleValue = BaseValue * condition_factor * (1 - haircut)
        - MaxBid = ResaleValue * max_bid_percent - costs
        """
        cat_config = self._get_category_config(category, config)
        
        # Extract brand and details
        brand, model = self._extract_brand_model(auction)
        
        # Determine tier
        tier = self._get_tier(brand)
        base_value = self.base_values.get(tier, self.base_values.get('low', 100))
        
        # Check condition factors
        condition = self._assess_condition(auction)
        condition_factor = self._get_condition_factor(condition)
        
        # Calculate raw resale value
        raw_resale = base_value * condition_factor
        
        # Apply haircut
        haircut = cat_config.get('haircut', 0.15)
        
        # Additional risk for missing items
        if condition.get('missing_box'):
            haircut += 0.10
        if condition.get('missing_papers'):
            haircut += 0.05
        if condition.get('not_working'):
            haircut += 0.20
        
        haircut = min(haircut, 0.50)  # Cap at 50%
        
        resale_value = raw_resale * (1 - haircut)
        
        # Calculate costs
        costs = self._calculate_costs(category, cat_config)
        
        # Calculate max bid
        max_bid_percent = cat_config.get('max_bid_percent', 0.70)
        max_bid = (resale_value * max_bid_percent) - costs
        max_bid = max(0, max_bid)
        
        # Calculate ROI and margin
        roi, margin = self._calculate_roi_and_margin(resale_value, max_bid, costs)
        
        # Determine confidence
        confidence = self._calculate_confidence(brand, condition)
        
        # Build notes
        notes = [
            f"Brand: {brand or 'Unknown'}",
            f"Tier: {tier}",
            f"Base value: €{base_value}",
            f"Condition factor: {condition_factor:.2f}",
            f"Haircut: {haircut*100:.0f}%",
        ]
        
        if model:
            notes.append(f"Model: {model}")
        
        # Risk factors
        risk_factors = []
        if condition.get('not_working'):
            risk_factors.append("Watch not working")
        if condition.get('missing_box'):
            risk_factors.append("Missing box")
        if condition.get('missing_papers'):
            risk_factors.append("Missing papers")
        if condition.get('uncertain_authenticity'):
            risk_factors.append("Authenticity uncertain")
        
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
                'brand': brand,
                'model': model,
                'tier': tier,
                'base_value': base_value,
                'condition_factor': condition_factor,
                'haircut': haircut,
                'condition': condition,
            }
        )
    
    def _extract_brand_model(self, auction: Auction) -> tuple:
        """Extract brand and model from auction."""
        text = (auction.title or '') + (auction.description or '')
        
        brand = None
        model = None
        
        # Check each tier's brands
        all_brands = []
        for tier, brands in self.brand_tiers.items():
            all_brands.extend(brands)
        
        # Find brand in text (case insensitive)
        for b in all_brands:
            if b.lower() in text.lower():
                brand = b
                break
        
        # Try to extract model
        # Model is often after brand
        if brand:
            brand_pos = text.lower().find(brand.lower())
            if brand_pos >= 0:
                # Get text after brand
                after_brand = text[brand_pos + len(brand):]
                # Extract potential model (first few words)
                words = after_brand.split()[:3]
                model = ' '.join(words) if words else None
        
        return brand, model
    
    def _get_tier(self, brand: Optional[str]) -> str:
        """Get tier for a brand."""
        if not brand:
            return 'low'
        
        for tier, brands in self.brand_tiers.items():
            if brand in brands:
                return tier
        
        return 'low'
    
    def _assess_condition(self, auction: Auction) -> Dict[str, bool]:
        """Assess watch condition from auction text."""
        text = ((auction.title or '') + (auction.description or '')).lower()
        
        condition = {
            'has_box': False,
            'has_papers': False,
            'working': True,
            'good_condition': False,
            'missing_box': False,
            'missing_papers': False,
            'not_working': False,
            'uncertain_authenticity': False,
        }
        
        # Check for positive indicators
        if 'con box' in text or 'scatola' in text or 'confezione' in text:
            condition['has_box'] = True
        
        if 'con documenti' in text or 'certificato' in text or 'garanzia' in text:
            condition['has_papers'] = True
        
        if 'funzionante' in text or 'funziona' in text or 'orologio funzionante' in text:
            condition['working'] = True
        
        if 'ottimo stato' in text or 'perfetto stato' in text or 'come nuovo' in text:
            condition['good_condition'] = True
        
        # Check for negative indicators
        if 'senza box' in text or 'senza scatola' in text or 'senza confezione' in text:
            condition['missing_box'] = True
        
        if 'senza documenti' in text or 'senza certificato' in text:
            condition['missing_papers'] = True
        
        if 'non funziona' in text or 'non funzionante' in text or 'non marcia' in text:
            condition['not_working'] = True
        
        if 'da verificare' in text or 'da autenticare' in text:
            condition['uncertain_authenticity'] = True
        
        return condition
    
    def _get_condition_factor(self, condition: Dict[str, bool]) -> float:
        """Calculate condition factor based on condition."""
        factor = 1.0
        
        if condition.get('good_condition'):
            factor *= 1.2
        
        if condition.get('working') and not condition.get('not_working'):
            factor *= 1.0
        else:
            factor *= 0.6
        
        if condition.get('has_box'):
            factor *= 1.1
        
        if condition.get('has_papers'):
            factor *= 1.1
        
        if condition.get('missing_box'):
            factor *= 0.9
        
        if condition.get('missing_papers'):
            factor *= 0.9
        
        if condition.get('not_working'):
            factor *= 0.5
        
        return max(0.1, factor)  # Minimum factor
    
    def _calculate_costs(self, category: AuctionCategory, cat_config: Dict[str, Any]) -> float:
        """Calculate total costs for watches."""
        commission = cat_config.get('commission_percent', 0.05)
        trasporto = cat_config.get('trasporto', 30)
        autenticazione = cat_config.get('autenticazione', 100)
        restauro = cat_config.get('restauro', 200)
        
        # Only add authentication if potentially needed
        # Only add restauro if mentioned
        text = ''  # Would need auction text here
        extra_costs = autenticazione if 'da verificare' in text.lower() else 0
        
        return trasporto + extra_costs
    
    def _calculate_confidence(self, brand: Optional[str], condition: Dict[str, bool]) -> str:
        """Calculate confidence level."""
        if not brand:
            return 'low'
        
        if brand in self.brand_tiers.get('luxury', []):
            if condition.get('has_box') and condition.get('has_papers'):
                return 'high'
            return 'medium'
        
        if condition.get('not_working') or condition.get('uncertain_authenticity'):
            return 'low'
        
        return 'medium'