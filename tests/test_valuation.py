"""
Tests for Valuation calculations.
"""
import pytest
from datetime import datetime

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.models import Auction, AuctionCategory, ValuationResult
from app.valuation.jewelry import JewelryValuator, GoldSpotCache
from app.valuation.watches import WatchValuator
from app.valuation.cars import AutoValuator
from app.valuation.realestate import RealEstateValuator
from app.valuation.costs import (
    calculate_roi,
    calculate_margin,
    calculate_max_bid,
    calculate_total_costs,
)


class TestJewelryValuation:
    """Test jewelry valuation."""
    
    def setup_method(self):
        self.gold_cache = GoldSpotCache(fallback_price=72.0)
        self.valuator = JewelryValuator(self.gold_cache)
        self.config = {
            'costs': {
                'gioiello': {
                    'commission_percent': 0.05,
                    'trasporto': 15,
                    'certificazione': 50,
                    'haircut': 0.20,
                    'max_bid_percent': 0.80,
                }
            }
        }
    
    def test_value_jewelry_with_grams(self):
        """Test valuing jewelry with grams and title."""
        auction = Auction(
            url="https://example.com/asta/1",
            title="Braccialetto oro 750",
            description="Braccialetto oro 750 grammi 10g",
            base_price=500,
        )
        
        result = self.valuator.valuate(auction, AuctionCategory.GIOIELLO, self.config)
        
        assert result is not None
        assert result.resale_value > 0
        assert result.max_bid > 0
        assert result.roi >= 0
    
    def test_fallback_valuation(self):
        """Test fallback when no grams."""
        auction = Auction(
            url="https://example.com/asta/2",
            title="Oggetto oro",
            base_price=100,
        )
        
        result = self.valuator.valuate(auction, AuctionCategory.GIOIELLO, self.config)
        # Should still return something with fallback
        assert result is not None


class TestWatchValuation:
    """Test watch valuation."""
    
    def setup_method(self):
        self.valuator = WatchValuator({
            'watch_brands': {
                'luxury': ['Rolex', 'Patek Philippe'],
                'high': ['Cartier', 'Tag Heuer'],
                'mid': ['Seiko', 'Citizen'],
                'low': ['Generic'],
            },
            'watch_values': {
                'luxury': 5000,
                'high': 1500,
                'mid': 300,
                'low': 100,
            }
        })
        self.config = {
            'costs': {
                'orologio': {
                    'commission_percent': 0.05,
                    'trasporto': 30,
                    'autenticazione': 100,
                    'haircut': 0.15,
                    'max_bid_percent': 0.70,
                }
            }
        }
    
    def test_value_rolex(self):
        """Test valuing a Rolex."""
        auction = Auction(
            url="https://example.com/asta/1",
            title="Orologio Rolex Submariner",
            description="Rolex usato con box",
            base_price=3000,
        )
        
        result = self.valuator.valuate(auction, AuctionCategory.OROLOGIO, self.config)
        
        assert result is not None
        assert result.resale_value > 0
        assert result.category == AuctionCategory.OROLOGIO
    
    def test_reduce_for_missing_docs(self):
        """Test that missing docs reduce value."""
        auction = Auction(
            url="https://example.com/asta/2",
            title="Orologio senza documenti",
            description="Orologio senza box né certificato",
            base_price=500,
        )
        
        result = self.valuator.valuate(auction, AuctionCategory.OROLOGIO, self.config)
        
        assert result is not None
        # Should have higher haircut due to missing docs
        assert result.risk_factors is not None


class TestAutoValuation:
    """Test vehicle valuation."""
    
    def setup_method(self):
        self.valuator = AutoValuator({
            'auto_tiers': {
                'luxury': ['Mercedes', 'BMW', 'Audi'],
                'premium': ['Volkswagen', 'Volvo'],
                'budget': ['Fiat', 'Lancia'],
            },
            'auto_values': {
                'luxury': [40000, 25000, 15000],
                'premium': [20000, 12000, 6000],
                'budget': [12000, 7000, 3500],
            }
        })
        self.config = {
            'costs': {
                'auto': {
                    'commission_percent': 0.05,
                    'trasporto': 200,
                    'passaggio_proprieta': 150,
                    'ripristino': 300,
                    'haircut': 0.15,
                    'max_bid_percent': 0.70,
                }
            }
        }
    
    def test_value_mercedes(self):
        """Test valuing a Mercedes."""
        auction = Auction(
            url="https://example.com/asta/1",
            title="Mercedes C220 CDi",
            description="Mercedes C220 diesel 2019 50000 km",
            base_price=15000,
        )
        
        result = self.valuator.valuate(auction, AuctionCategory.AUTO, self.config)
        
        assert result is not None
        assert result.category == AuctionCategory.AUTO
    
    def test_high_risk_for_not_working(self):
        """Test high risk for non-working vehicle."""
        auction = Auction(
            url="https://example.com/asta/2",
            title="Auto non funziona",
            description="Veicolo non marcia senza chiavi",
            base_price=500,
        )
        
        result = self.valuator.valuate(auction, AuctionCategory.AUTO, self.config)
        
        assert result is not None
        assert len(result.risk_factors) > 0


class TestRealEstateValuation:
    """Test real estate valuation."""
    
    def setup_method(self):
        self.valuator = RealEstateValuator({
            'omi_min_by_area': {
                'Milano': {'centro': 4500, 'semicentro': 3500},
                'Roma': {'centro': 4000, 'semicentro': 3000},
                'DEFAULT': {'DEFAULT': 1200},
            }
        })
        self.config = {
            'costs': {
                'immobile': {
                    'commission_percent': 0.05,
                    'imposte_registro': 0.02,
                    'altre_spese': 2000,
                    'lavori_stimati': 5000,
                    'haircut': 0.05,
                    'max_bid_percent': 0.65,
                }
            }
        }
    
    def test_value_apartment(self):
        """Test valuing an apartment."""
        auction = Auction(
            url="https://example.com/asta/1",
            title="Appartamento 80 MQ Milano",
            description="Appartamento 3 vani zona semicentro",
            base_price=80000,
        )
        
        result = self.valuator.valuate(auction, AuctionCategory.IMMOBILE, self.config)
        
        assert result is not None
        assert result.resale_value > 0


class TestCostCalculations:
    """Test cost calculation functions."""
    
    def test_calculate_roi(self):
        """Test ROI calculation."""
        roi = calculate_roi(
            resale_value=15000,
            bid_amount=10000,
            costs=2000,
        )
        
        # Margin = 15000 - 12000 = 3000
        # ROI = 3000 / 12000 = 0.25
        assert roi == 0.25
    
    def test_calculate_margin(self):
        """Test margin calculation."""
        margin = calculate_margin(
            resale_value=15000,
            bid_amount=10000,
            costs=2000,
        )
        
        assert margin == 3000
    
    def test_calculate_max_bid(self):
        """Test max bid calculation."""
        max_bid = calculate_max_bid(
            resale_value=10000,
            category='auto',
            config={
                'costs': {
                    'auto': {
                        'max_bid_percent': 0.70,
                        'trasporto': 200,
                        'passaggio_proprieta': 150,
                        'ripristino': 300,
                    }
                }
            }
        )
        
        # Max bid = 10000 * 0.70 - 650 = 6350
        assert max_bid == 6350
    
    def test_calculate_total_costs(self):
        """Test total costs calculation."""
        costs = calculate_total_costs(
            category='auto',
            config={
                'costs': {
                    'auto': {
                        'trasporto': 200,
                        'passaggio_proprieta': 150,
                        'ripristino': 300,
                    }
                }
            }
        )
        
        assert costs == 650


class TestValuationResult:
    """Test ValuationResult model."""
    
    def test_to_opportunity(self):
        """Test converting ValuationResult to Opportunity."""
        result = ValuationResult(
            category=AuctionCategory.AUTO,
            resale_value=15000,
            max_bid=8000,
            total_costs=1000,
            roi=0.30,
            margin=4000,
            confidence='high',
            notes=['Note 1', 'Note 2'],
            risk_factors=['Risk 1'],
        )
        
        auction = Auction(
            url="https://example.com/asta/1",
            title="Test Auction",
        )
        
        opportunity = result.to_opportunity(auction)
        
        assert opportunity.auction == auction
        assert opportunity.category == AuctionCategory.AUTO
        assert opportunity.estimated_roi == 0.30