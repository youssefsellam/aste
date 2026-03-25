"""
Tests for Auction Classifier.
"""
import pytest
from datetime import datetime

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.models import Auction, AuctionCategory
from app.classify.classifier import AuctionClassifier
from app.classify.keywords import (
    JEWELRY_KEYWORDS,
    AUTO_KEYWORDS,
    WATCH_KEYWORDS,
    REAL_ESTATE_KEYWORDS,
)


class TestClassifier:
    """Test auction classifier."""
    
    def setup_method(self):
        self.classifier = AuctionClassifier()
    
    def test_classify_jewelry(self):
        """Test classification of jewelry."""
        auction = Auction(
            url="https://example.com/asta/1",
            title="BRACCIALETTO ORO GIALLO TITOLO 750 GR. 4,10",
            description="Braccialetto in oro 750",
        )
        
        category, confidence = self.classifier.classify(auction)
        assert category == AuctionCategory.GIOIELLO
        assert confidence > 0
    
    def test_classify_watch(self):
        """Test classification of watch."""
        auction = Auction(
            url="https://example.com/asta/2",
            title="Orologio Rolex Submariner",
            description="Orologio usato in ottime condizioni",
        )
        
        category, confidence = self.classifier.classify(auction)
        assert category == AuctionCategory.OROLOGIO
    
    def test_classify_auto(self):
        """Test classification of vehicle."""
        auction = Auction(
            url="https://example.com/asta/3",
            title="AUTOVETTURA MERCEDES C220 CDi",
            description="Auto diesel anno 2019 km 45000",
        )
        
        category, confidence = self.classifier.classify(auction)
        assert category == AuctionCategory.AUTO
    
    def test_classify_real_estate(self):
        """Test classification of real estate."""
        auction = Auction(
            url="https://example.com/asta/4",
            title="APPARTAMENTO 85 MQ",
            description="Appartamento 3 locali zona centro",
        )
        
        category, confidence = self.classifier.classify(auction)
        assert category == AuctionCategory.IMMOBILE
    
    def test_classify_unknown(self):
        """Test classification when unknown."""
        auction = Auction(
            url="https://example.com/asta/5",
            title="Oggetto generico",
            description="Descrizione generica senza keyword",
        )
        
        category, confidence = self.classifier.classify(auction)
        # Should be altro or unknown
        assert category in [AuctionCategory.ALTRO, AuctionCategory.UNKNOWN]


class TestKeywordMatching:
    """Test keyword matching."""
    
    def test_jewelry_keywords(self):
        """Test jewelry keywords are defined."""
        assert 'oro' in JEWELRY_KEYWORDS
        assert '750' in JEWELRY_KEYWORDS or 'oro 750' in JEWELRY_KEYWORDS
        assert 'anello' in JEWELRY_KEYWORDS
    
    def test_watch_keywords(self):
        """Test watch keywords are defined."""
        assert 'rolex' in WATCH_KEYWORDS
        assert 'orologio' in WATCH_KEYWORDS
        assert 'omega' in WATCH_KEYWORDS
    
    def test_auto_keywords(self):
        """Test auto keywords are defined."""
        assert 'autovettura' in AUTO_KEYWORDS
        assert 'diesel' in AUTO_KEYWORDS
        assert 'mercedes' in AUTO_KEYWORDS
    
    def test_real_estate_keywords(self):
        """Test real estate keywords are defined."""
        assert 'appartamento' in REAL_ESTATE_KEYWORDS
        assert 'mq' in REAL_ESTATE_KEYWORDS
        assert 'garage' in REAL_ESTATE_KEYWORDS


class TestRiskDetection:
    """Test risk factor detection."""
    
    def setup_method(self):
        self.classifier = AuctionClassifier()
    
    def test_detect_high_risk_keywords(self):
        """Test detection of high risk keywords."""
        auction = Auction(
            url="https://example.com/asta/rischio",
            title="Auto non funziona",
            description="Veicolo senza chiavi e senza documenti",
        )
        
        risks = self.classifier.detect_risk_factors(auction)
        assert len(risks) > 0
    
    def test_no_risk_for_clean_auction(self):
        """Test no risk for clean auction."""
        auction = Auction(
            url="https://example.com/asta/clean",
            title="Orologio Rolex completo",
            description="Con box e documenti, funzionante",
        )
        
        risks = self.classifier.detect_risk_factors(auction)
        # Should have minimal or no risks
        assert len(risks) <= 2


class TestBrandExtraction:
    """Test brand extraction."""
    
    def setup_method(self):
        self.classifier = AuctionClassifier(config={
            'watch_brands': {
                'luxury': ['Rolex', 'Patek Philippe'],
                'high': ['Cartier', 'Tag Heuer'],
                'mid': ['Seiko', 'Citizen'],
                'low': ['Generic'],
            },
            'auto_tiers': {
                'luxury': ['Mercedes', 'BMW', 'Audi'],
                'premium': ['Volkswagen', 'Volvo'],
                'budget': ['Fiat', 'Lancia'],
            }
        })
    
    def test_extract_watch_brand(self):
        """Test extracting watch brand."""
        auction = Auction(
            url="https://example.com/asta/1",
            title="Orologio Rolex Datejust",
            description="Usato",
        )
        
        brand = self.classifier.extract_brand(auction, AuctionCategory.OROLOGIO)
        assert brand == 'Rolex'
    
    def test_extract_auto_brand(self):
        """Test extracting auto brand."""
        auction = Auction(
            url="https://example.com/asta/2",
            title="Mercedes C220",
            description="Anno 2020",
        )
        
        brand = self.classifier.extract_brand(auction, AuctionCategory.AUTO)
        assert brand == 'Mercedes'