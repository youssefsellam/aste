"""
Valuation for vehicles (cars, motorcycles, etc.).
"""
import re
import logging
from typing import Optional, Dict, Any

from ..models import Auction, AuctionCategory, ValuationResult
from .base import BaseValuator


logger = logging.getLogger(__name__)


class AutoValuator(BaseValuator):
    """
    Valuator for vehicles (cars, motorcycles, trucks).
    
    Uses brand tier system and vehicle specifics to estimate resale value.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        
        # Auto brand tiers from config
        self.auto_tiers = self.config.get('auto_tiers', {
            'luxury': ['Mercedes', 'BMW', 'Audi', 'Porsche'],
            'premium': ['Volkswagen', 'Volvo', 'Peugeot', 'Citroen'],
            'budget': ['Fiat', 'Lancia', 'Ford', 'Opel'],
        })
        
        # Base values by tier and age [new, mid, old]
        self.base_values = self.config.get('auto_values', {
            'luxury': [40000, 25000, 15000],
            'premium': [20000, 12000, 6000],
            'budget': [12000, 7000, 3500],
        })
    
    def valuate(
        self,
        auction: Auction,
        category: AuctionCategory,
        config: Dict[str, Any],
    ) -> Optional[ValuationResult]:
        """
        Value a vehicle auction.
        
        Formula:
        - Identify brand, year, km
        - Determine age category
        - Apply mileage factor
        - ResaleValue = BaseValue * mileage_factor * (1 - haircut)
        - MaxBid = ResaleValue * max_bid_percent - costs
        """
        cat_config = self._get_category_config(category, config)
        
        # Extract vehicle details
        details = self._extract_vehicle_details(auction)
        
        # Determine tier
        tier = self._get_tier(details.get('brand'))
        
        # Get age category and base value
        age_category = self._get_age_category(details.get('year'))
        tier_values = self.base_values.get(tier, self.base_values.get('budget', [12000, 7000, 3500]))
        base_value = tier_values[age_category] if age_category < len(tier_values) else tier_values[-1]
        
        # Calculate mileage factor
        mileage_factor = self._calculate_mileage_factor(details.get('km', 0))
        
        # Calculate raw resale value
        raw_resale = base_value * mileage_factor
        
        # Apply haircut
        haircut = cat_config.get('haircut', 0.15)
        
        # Additional risk factors
        if details.get('not_working'):
            haircut += 0.20
        if details.get('no_keys'):
            haircut += 0.15
        if details.get('administrative_hold'):
            haircut += 0.25
        
        haircut = min(haircut, 0.60)  # Cap at 60%
        
        resale_value = raw_resale * (1 - haircut)
        
        # Calculate costs
        costs = self._calculate_costs(category, cat_config, details)
        
        # Calculate max bid
        max_bid_percent = cat_config.get('max_bid_percent', 0.70)
        max_bid = (resale_value * max_bid_percent) - costs
        max_bid = max(0, max_bid)
        
        # Calculate ROI and margin
        roi, margin = self._calculate_roi_and_margin(resale_value, max_bid, costs)
        
        # Determine confidence
        confidence = self._calculate_confidence(details)
        
        # Build notes
        notes = [
            f"Brand: {details.get('brand', 'Unknown')}",
            f"Tier: {tier}",
            f"Year: {details.get('year', 'N/A')}",
            f"Km: {details.get('km', 0):,}" if details.get('km') else "Km: N/A",
            f"Base value: €{base_value}",
            f"Mileage factor: {mileage_factor:.2f}",
            f"Haircut: {haircut*100:.0f}%",
        ]
        
        if details.get('fuel'):
            notes.append(f"Fuel: {details.get('fuel')}")
        
        # Risk factors
        risk_factors = []
        if details.get('not_working'):
            risk_factors.append("Vehicle not working")
        if details.get('no_keys'):
            risk_factors.append("Missing keys")
        if details.get('administrative_hold'):
            risk_factors.append("Administrative hold")
        if details.get('missing_docs'):
            risk_factors.append("Missing documents")
        
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
                'brand': details.get('brand'),
                'year': details.get('year'),
                'km': details.get('km'),
                'fuel': details.get('fuel'),
                'tier': tier,
                'age_category': age_category,
                'base_value': base_value,
                'mileage_factor': mileage_factor,
                'haircut': haircut,
                'details': details,
            }
        )
    
    def _extract_vehicle_details(self, auction: Auction) -> Dict[str, Any]:
        """Extract vehicle details from auction."""
        text = (auction.title or '') + (auction.description or '')
        text_lower = text.lower()
        
        details = {
            'brand': None,
            'model': None,
            'year': None,
            'km': None,
            'fuel': None,
            'not_working': False,
            'no_keys': False,
            'administrative_hold': False,
            'missing_docs': False,
        }
        
        # Extract brand
        all_brands = []
        for tier, brands in self.auto_tiers.items():
            all_brands.extend(brands)
        
        for brand in all_brands:
            if brand.lower() in text_lower:
                details['brand'] = brand
                break
        
        # Extract year
        year_patterns = [
            r'anno\s*(\d{4})',
            r'immatricolat.*?(\d{4})',
            r'(\d{4})\s*immatr',
            r'(?:prima\s+)?(?:immatricolazion|registrazion).*?(\d{4})',
        ]
        
        for pattern in year_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    year = int(match.group(1))
                    if 1970 <= year <= 2030:
                        details['year'] = year
                        break
                except ValueError:
                    pass
        
        # Extract km
        km_patterns = [
            r'(\d{1,3}(?:\.\d{3})*)\s*km',
            r'chilometri\s*[:\s]*(\d+)',
            r'km\s*[:\s]*(\d+)',
        ]
        
        for pattern in km_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    km_str = match.group(1).replace('.', '')
                    details['km'] = int(km_str)
                    break
                except ValueError:
                    pass
        
        # Extract fuel type
        fuel_types = ['diesel', 'benzina', 'elettrico', 'ibrido', 'metano', 'gpl']
        for fuel in fuel_types:
            if fuel in text_lower:
                details['fuel'] = fuel
                break
        
        # Check condition flags
        if any(k in text_lower for k in ['non funziona', 'non marcia', 'non avviabile']):
            details['not_working'] = True
        
        if any(k in text_lower for k in ['senza chiavi', 'chiavi mancanti']):
            details['no_keys'] = True
        
        if any(k in text_lower for k in ['fermo amministrativo', 'precetto', 'ipoteca']):
            details['administrative_hold'] = True
        
        if any(k in text_lower for k in ['senza documenti', 'documenti mancanti', 'libretto mancante']):
            details['missing_docs'] = True
        
        return details
    
    def _get_tier(self, brand: Optional[str]) -> str:
        """Get tier for a brand."""
        if not brand:
            return 'budget'
        
        for tier, brands in self.auto_tiers.items():
            if brand in brands:
                return tier
        
        return 'budget'
    
    def _get_age_category(self, year: Optional[int]) -> int:
        """
        Get age category: 0 = new (<2 years), 1 = mid (2-5 years), 2 = old (>5 years)
        """
        if not year:
            return 1  # Default to mid
        
        from datetime import datetime
        current_year = datetime.now().year
        age = current_year - year
        
        if age < 2:
            return 0
        elif age < 5:
            return 1
        else:
            return 2
    
    def _calculate_mileage_factor(self, km: int) -> float:
        """Calculate mileage factor based on km."""
        if km is None or km == 0:
            return 1.0
        
        # Typical annual mileage ~15,000 km
        if km < 30000:
            return 1.1
        elif km < 60000:
            return 1.0
        elif km < 100000:
            return 0.85
        elif km < 150000:
            return 0.70
        elif km < 200000:
            return 0.55
        else:
            return 0.40
    
    def _calculate_costs(
        self,
        category: AuctionCategory,
        cat_config: Dict[str, Any],
        details: Dict[str, Any],
    ) -> float:
        """Calculate total costs for vehicles."""
        trasporto = cat_config.get('trasporto', 200)
        passaggio = cat_config.get('passaggio_proprieta', 150)
        ripristino = cat_config.get('ripristino', 300)
        
        # Adjust ripristino based on condition
        if details.get('not_working'):
            ripristino += 500
        if details.get('no_keys'):
            ripristino += 200
        
        return trasporto + passaggio + ripristino
    
    def _calculate_confidence(self, details: Dict[str, Any]) -> str:
        """Calculate confidence level."""
        # Low confidence if missing key info
        if not details.get('brand') and not details.get('year'):
            return 'low'
        
        if details.get('not_working') or details.get('administrative_hold'):
            return 'low'
        
        if details.get('brand') and details.get('year') and details.get('km'):
            return 'high'
        
        return 'medium'