"""
Valuation for real estate (apartments, houses, land, etc.).
"""
import re
import logging
from typing import Optional, Dict, Any

from ..models import Auction, AuctionCategory, ValuationResult
from .base import BaseValuator


logger = logging.getLogger(__name__)


class RealEstateValuator(BaseValuator):
    """
    Valuator for real estate properties.
    
    Uses OMI (Osservatorio Mercato Immobiliare) data or fallback heuristics.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        
        # OMI minimum values by area (€/mq)
        self.omi_min = self.config.get('omi_min_by_area', {
            'DEFAULT': {'DEFAULT': 1200}
        })
    
    def valuate(
        self,
        auction: Auction,
        category: AuctionCategory,
        config: Dict[str, Any],
    ) -> Optional[ValuationResult]:
        """
        Value a real estate auction.
        
        Formula:
        - Extract mq, rooms, location
        - Find OMI reference or use fallback
        - ResaleValue = mq * omi_value * (1 - haircut)
        - MaxBid = ResaleValue * max_bid_percent - costs
        """
        cat_config = self._get_category_config(category, config)
        
        # Extract property details
        details = self._extract_property_details(auction)
        
        # Get OMI reference value
        omi_value = self._get_omi_value(details)
        
        # Calculate raw resale value
        mq = details.get('mq', 0)
        if mq <= 0 or omi_value <= 0:
            # Fallback to base price
            base_price = auction.base_price or auction.current_price or 0
            if base_price <= 0:
                return None
            
            resale_value = base_price * 1.15  # Assume 15% margin on base
        else:
            raw_resale = mq * omi_value
            # Apply haircut
            haircut = cat_config.get('haircut', 0.05)
            
            # Additional risk factors
            if details.get('state_grezzo'):
                haircut += 0.10
            if details.get('needs_work'):
                haircut += 0.15
            if details.get('occupied'):
                haircut += 0.20
            
            haircut = min(haircut, 0.40)
            resale_value = raw_resale * (1 - haircut)
        
        # Calculate costs
        costs = self._calculate_costs(category, cat_config, details)
        
        # Calculate max bid
        max_bid_percent = cat_config.get('max_bid_percent', 0.65)
        max_bid = (resale_value * max_bid_percent) - costs
        max_bid = max(0, max_bid)
        
        # Calculate ROI and margin
        roi, margin = self._calculate_roi_and_margin(resale_value, max_bid, costs)
        
        # Determine confidence
        confidence = self._calculate_confidence(details, omi_value)
        
        # Build notes
        notes = [
            f"Property type: {details.get('property_type', 'Unknown')}",
            f"MQ: {details.get('mq', 'N/A')}",
            f"Rooms: {details.get('rooms', 'N/A')}",
            f"Location: {details.get('location', 'N/A')}",
            f"OMI value: €{omi_value}/mq" if omi_value > 0 else "OMI: Using fallback",
            f"Haircut: {haircut*100:.0f}%" if 'haircut' in dir() else "",
        ]
        
        # Risk factors
        risk_factors = []
        if details.get('state_grezzo'):
            risk_factors.append("Property in raw state")
        if details.get('needs_work'):
            risk_factors.append("Needs renovation work")
        if details.get('occupied'):
            risk_factors.append("Property is occupied")
        if details.get('has_oneri'):
            risk_factors.append("Has additional charges/liens")
        
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
                'mq': details.get('mq'),
                'rooms': details.get('rooms'),
                'location': details.get('location'),
                'property_type': details.get('property_type'),
                'omi_value': omi_value,
                'details': details,
            }
        )
    
    def _extract_property_details(self, auction: Auction) -> Dict[str, Any]:
        """Extract property details from auction."""
        text = (auction.title or '') + (auction.description or '')
        text_lower = text.lower()
        
        details = {
            'mq': None,
            'rooms': None,
            'location': None,
            'property_type': None,
            'floor': None,
            'state_grezzo': False,
            'needs_work': False,
            'occupied': False,
            'has_oneri': False,
        }
        
        # Extract mq
        mq_patterns = [
            r'(\d+)\s*mq',
            r'metri\s*quadri\s*[:\s]*(\d+)',
            r'superficie\s*[:\s]*(\d+)\s*mq',
            r'di\s*(\d+)\s*m',
        ]
        
        for pattern in mq_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    details['mq'] = int(match.group(1))
                    break
                except ValueError:
                    pass
        
        # Extract rooms/vani
        rooms_patterns = [
            r'(\d+)\s*(?:vani|locali|camere)',
            r'(\d+)\s*(?:stanza|stanze)',
        ]
        
        for pattern in rooms_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    details['rooms'] = int(match.group(1))
                    break
                except ValueError:
                    pass
        
        # Extract location
        location_patterns = [
            r'ubicat[oa]\s*[:\s]*([^\n,]+)',
            r'località\s*[:\s]*([^\n,]+)',
            r'in\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s*,?\s*[A-Z]{2}',
            r'a\s+([A-Z][a-z]+)\s*,',
        ]
        
        for pattern in location_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                location = match.group(1).strip()
                # Clean up
                location = re.sub(r'\s+', ' ', location)[:50]
                details['location'] = location
                break
        
        # Extract property type
        property_types = {
            'appartamento': 'appartamento',
            'villa': 'villa',
            'villino': 'villa',
            'garage': 'garage',
            'box': 'box',
            'cantina': 'cantina',
            'ufficio': 'ufficio',
            'negozio': 'negozio',
            'magazzino': 'magazzino',
            'terreno': 'terreno',
            'area': 'terreno',
            'capannone': 'capannone',
        }
        
        for ptype, ptype_clean in property_types.items():
            if ptype in text_lower:
                details['property_type'] = ptype_clean
                break
        
        # Extract floor
        floor_patterns = [
            r'piano\s*(-?\d+|terra|rialzato|seminterrato)',
            r'(\d+)°\s*piano',
        ]
        
        for pattern in floor_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                details['floor'] = match.group(1)
                break
        
        # Check condition flags
        if any(k in text_lower for k in ['stato grezzo', 'non finito', 'da finire']):
            details['state_grezzo'] = True
        
        if any(k in text_lower for k in ['da ripristinare', 'da sistemare', 'da ristrutturare', 'lavori']):
            details['needs_work'] = True
        
        if any(k in text_lower for k in ['occupato', 'locato', 'affittato']):
            details['occupied'] = True
        
        if any(k in text_lower for k in ['oneri', 'gravami', 'ipoteca', 'trattenuta']):
            details['has_oneri'] = True
        
        return details
    
    def _get_omi_value(self, details: Dict[str, Any]) -> float:
        """
        Get OMI reference value for the property.
        
        Returns OMI value in €/mq or 0 if not available.
        """
        location = details.get('location', '')
        
        if not location:
            return 0
        
        # Try to find city in OMI data
        # Look for city name in location
        location_upper = location.upper()
        
        # Check each city in OMI config
        for city, zones in self.omi_min.items():
            if city == 'DEFAULT':
                continue
            
            if city in location_upper or location_upper.startswith(city):
                # Found the city, check zones
                # Default to semicentro if can't determine exact zone
                default_zone = zones.get('semicentro', zones.get('DEFAULT', 0))
                return default_zone
        
        # If no match, try to use any city's DEFAULT
        for city, zones in self.omi_min.items():
            if 'DEFAULT' in zones:
                return zones['DEFAULT']
        
        return 0
    
    def _calculate_costs(
        self,
        category: AuctionCategory,
        cat_config: Dict[str, Any],
        details: Dict[str, Any],
    ) -> float:
        """Calculate total costs for real estate."""
        commission = cat_config.get('commission_percent', 0.05)
        imposte = cat_config.get('imposte_registro', 0.02)  # 2%
        altre_spese = cat_config.get('altre_spese', 2000)
        lavori_stimati = cat_config.get('lavori_stimati', 5000)
        
        # Adjust based on condition
        if details.get('needs_work'):
            lavori_stimati += 3000
        if details.get('state_grezzo'):
            lavori_stimati += 5000
        
        return altre_spese + lavori_stimati
    
    def _calculate_confidence(self, details: Dict[str, Any], omi_value: float) -> str:
        """Calculate confidence level."""
        # High confidence if we have mq and OMI value
        if details.get('mq') and omi_value > 0:
            return 'high'
        
        # Medium if we have some data
        if details.get('mq') or details.get('location'):
            return 'medium'
        
        return 'low'