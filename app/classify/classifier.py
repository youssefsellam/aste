"""
Classifier for categorizing auctions.
"""
import re
import logging
from typing import Optional, Dict, Any, Tuple, List
from collections import Counter

from ..models import Auction, AuctionCategory
from .keywords import (
    JEWELRY_KEYWORDS,
    WATCH_KEYWORDS,
    AUTO_KEYWORDS,
    REAL_ESTATE_KEYWORDS,
    HIGH_RISK_KEYWORDS,
    POSITIVE_KEYWORDS,
    get_all_category_keywords,
)


logger = logging.getLogger(__name__)


class AuctionClassifier:
    """
    Classifier for categorizing auctions based on keywords and patterns.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize classifier.
        
        Args:
            config: Configuration dictionary with brand tiers etc.
        """
        self.config = config or {}
        self.category_keywords = get_all_category_keywords()
        
        # Get brand tiers from config
        self.watch_brands = self.config.get('watch_brands', {
            'luxury': ['Rolex', 'Patek Philippe'],
            'high': ['Cartier', 'Tag Heuer'],
            'mid': ['Seiko', 'Citizen'],
            'low': ['Generic']
        })
        
        self.auto_tiers = self.config.get('auto_tiers', {
            'luxury': ['Mercedes', 'BMW', 'Audi'],
            'premium': ['Volkswagen', 'Volvo', 'Peugeot'],
            'budget': ['Fiat', 'Lancia', 'Ford']
        })
    
    def classify(self, auction: Auction) -> Tuple[AuctionCategory, float]:
        """
        Classify an auction into a category.
        
        Args:
            auction: Auction to classify
            
        Returns:
            Tuple of (category, confidence score 0-1)
        """
        # Combine title and description for analysis
        text = self._get_combined_text(auction)
        text_lower = text.lower()
        
        # Count keyword matches per category
        scores = {}
        
        for category, keywords in self.category_keywords.items():
            matches = sum(1 for kw in keywords if kw.lower() in text_lower)
            scores[category] = matches
        
        # Check for watch-specific patterns (watches are a subset of jewelry)
        if 'gioiello' in scores:
            # If there are watch-specific keywords, boost watches
            watch_matches = sum(1 for kw in WATCH_KEYWORDS if kw in text_lower)
            if watch_matches > 0:
                scores['orologio'] = scores.get('orologio', 0) + watch_matches
        
        # Check for auto
        if 'auto' in scores:
            # Check for vehicle-related patterns
            auto_patterns = [
                r'\d{4}',  # Year
                r'\d+\s*km',
                r'(?:benzina|diesel|elettrico|ibrido)',
                r'targa',
                r'immatricolat',
            ]
            auto_pattern_score = sum(
                len(re.findall(p, text_lower)) 
                for p in auto_patterns
            )
            scores['auto'] = scores.get('auto', 0) + auto_pattern_score
        
        # Check for real estate
        if 'immobile' in scores:
            # Check for property patterns
            property_patterns = [
                r'\d+\s*mq',
                r'metri\s*quadri',
                r'piano\s*\d',
                r'appartamento',
                r'villa',
                r'garage',
            ]
            prop_pattern_score = sum(
                len(re.findall(p, text_lower)) 
                for p in property_patterns
            )
            scores['immobile'] = scores.get('immobile', 0) + prop_pattern_score
        
        # Determine category
        if not scores or max(scores.values()) == 0:
            return AuctionCategory.ALTRO, 0.5
        
        # Get best category
        best_category = max(scores, key=scores.get)
        best_score = scores[best_category]
        
        # Calculate confidence
        total_keywords = sum(scores.values())
        confidence = min(best_score / max(total_keywords, 1), 1.0)
        
        # Map to AuctionCategory
        category_map = {
            'gioiello': AuctionCategory.GIOIELLO,
            'orologio': AuctionCategory.OROLOGIO,
            'auto': AuctionCategory.AUTO,
            'immobile': AuctionCategory.IMMOBILE,
        }
        
        return category_map.get(best_category, AuctionCategory.ALTRO), confidence
    
    def _get_combined_text(self, auction: Auction) -> str:
        """Get combined text for analysis."""
        parts = [
            auction.title or '',
            auction.description or '',
            auction.location or '',
            auction.tribunal or '',
            auction.raw_data.get('raw_text', ''),
        ]
        return ' '.join(p for p in parts if p)
    
    def detect_risk_factors(self, auction: Auction) -> List[str]:
        """
        Detect risk factors from auction text.
        
        Args:
            auction: Auction to analyze
            
        Returns:
            List of risk factor strings
        """
        text = self._get_combined_text(auction).lower()
        risk_factors = []
        
        for keyword in HIGH_RISK_KEYWORDS:
            if keyword in text:
                risk_factors.append(f"Risk keyword: {keyword}")
        
        # Check for missing documents/keys
        if 'senza chiavi' in text or 'chiavi mancanti' in text:
            risk_factors.append("Missing keys")
        
        if 'senza documenti' in text or 'documenti mancanti' in text:
            risk_factors.append("Missing documents")
        
        # Check for non-working
        if any(kw in text for kw in ['non funziona', 'non marcia', 'non funzionante']):
            risk_factors.append("Not working / not running")
        
        # Check for administrative hold
        if 'fermo amministrativo' in text or 'precetto' in text:
            risk_factors.append("Administrative hold / lien")
        
        return risk_factors
    
    def extract_brand(self, auction: Auction, category: AuctionCategory) -> Optional[str]:
        """
        Extract brand from auction based on category.
        
        Args:
            auction: Auction to analyze
            category: Category of the auction
            
        Returns:
            Brand name or None
        """
        text = self._get_combined_text(auction)
        
        if category == AuctionCategory.OROLOGIO:
            # Check watch brands
            brands = []
            for tier, brand_list in self.watch_brands.items():
                brands.extend(brand_list)
            
            for brand in brands:
                if brand.lower() in text.lower():
                    return brand
        
        elif category == AuctionCategory.AUTO:
            # Check auto brands
            brands = []
            for tier, brand_list in self.auto_tiers.items():
                brands.extend(brand_list)
            
            # Extract first word as potential brand
            words = text.split()
            for word in words[:5]:  # Check first few words
                for brand in brands:
                    if brand.lower() == word.lower():
                        return brand
        
        return None
    
    def is_profitable_category(self, category: AuctionCategory) -> bool:
        """Check if category is worth monitoring."""
        return category in [
            AuctionCategory.AUTO,
            AuctionCategory.IMMOBILE,
            AuctionCategory.GIOIELLO,
            AuctionCategory.OROLOGIO,
        ]


def classify_auction(
    auction: Auction,
    config: Optional[Dict[str, Any]] = None,
) -> Tuple[AuctionCategory, float]:
    """
    Convenience function to classify an auction.
    
    Args:
        auction: Auction to classify
        config: Optional configuration
        
    Returns:
        Tuple of (category, confidence)
    """
    classifier = AuctionClassifier(config)
    return classifier.classify(auction)


def detect_risks(auction: Auction) -> List[str]:
    """
    Convenience function to detect risk factors.
    
    Args:
        auction: Auction to analyze
        
    Returns:
        List of risk factor strings
    """
    classifier = AuctionClassifier()
    return classifier.detect_risk_factors(auction)