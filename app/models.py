"""
Data models for Fallco Aste Bot.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any, List
from enum import Enum
import hashlib
import json


class AuctionCategory(Enum):
    """Categories for auction classification."""
    AUTO = "auto"
    IMMOBILE = "immobile"
    GIOIELLO = "gioiello"
    OROLOGIO = "orologio"
    ALTRO = "altro"
    UNKNOWN = "unknown"


class AuctionStatus(Enum):
    """Status of auction in the system."""
    SEEN = "seen"
    EXPIRED = "expired"
    OPPORTUNITY = "opportunity"
    ALERTED = "alerted"


@dataclass
class Auction:
    """
    Represents an auction listing from Fallco.
    """
    url: str
    title: str
    category: Optional[AuctionCategory] = None
    current_price: Optional[float] = None
    base_price: Optional[float] = None
    end_datetime: Optional[datetime] = None
    start_datetime: Optional[datetime] = None
    location: Optional[str] = None
    tribunal: Optional[str] = None
    procedure_number: Optional[str] = None
    description: Optional[str] = None
    images: List[str] = field(default_factory=list)
    raw_data: Dict[str, Any] = field(default_factory=dict)
    first_seen: datetime = field(default_factory=datetime.now)
    last_seen: datetime = field(default_factory=datetime.now)

    @property
    def auction_hash(self) -> str:
        """Generate a unique hash for this auction."""
        content = f"{self.url}"
        return hashlib.md5(content.encode()).hexdigest()

    @property
    def minutes_to_end(self) -> Optional[int]:
        """Calculate minutes until auction ends."""
        if self.end_datetime:
            delta = self.end_datetime - datetime.now()
            return max(0, int(delta.total_seconds() / 60))
        return None

    @property
    def is_expiring_soon(self) -> bool:
        """Check if auction is expiring within horizon."""
        mins = self.minutes_to_end
        return mins is not None and mins <= 60

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            'url': self.url,
            'title': self.title,
            'category': self.category.value if self.category else None,
            'current_price': self.current_price,
            'base_price': self.base_price,
            'end_datetime': self.end_datetime.isoformat() if self.end_datetime else None,
            'start_datetime': self.start_datetime.isoformat() if self.start_datetime else None,
            'location': self.location,
            'tribunal': self.tribunal,
            'procedure_number': self.procedure_number,
            'description': self.description,
            'images': self.images,
            'first_seen': self.first_seen.isoformat(),
            'last_seen': self.last_seen.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Auction':
        """Create Auction from dictionary."""
        category = None
        if data.get('category'):
            try:
                category = AuctionCategory(data['category'])
            except ValueError:
                pass

        return cls(
            url=data['url'],
            title=data['title'],
            category=category,
            current_price=data.get('current_price'),
            base_price=data.get('base_price'),
            end_datetime=datetime.fromisoformat(data['end_datetime']) if data.get('end_datetime') else None,
            start_datetime=datetime.fromisoformat(data['start_datetime']) if data.get('start_datetime') else None,
            location=data.get('location'),
            tribunal=data.get('tribunal'),
            procedure_number=data.get('procedure_number'),
            description=data.get('description'),
            images=data.get('images', []),
            raw_data=data.get('raw_data', {}),
            first_seen=datetime.fromisoformat(data.get('first_seen', datetime.now().isoformat())),
            last_seen=datetime.fromisoformat(data.get('last_seen', datetime.now().isoformat())),
        )


@dataclass
class Opportunity:
    """
    Represents a profitable opportunity detected from an auction.
    """
    auction: Auction
    category: AuctionCategory
    resale_value: float
    max_bid: float
    estimated_costs: float
    estimated_roi: float
    estimated_margin: float
    notes: List[str] = field(default_factory=list)
    risk_factors: List[str] = field(default_factory=list)
    detected_at: datetime = field(default_factory=datetime.now)

    @property
    def is_profitable(self) -> bool:
        """Check if opportunity meets ROI threshold."""
        return self.estimated_roi >= 0.30

    @property
    def summary(self) -> str:
        """Get a short summary of the opportunity."""
        return f"{self.category.value.upper()}: {self.auction.title[:50]}... | ROI: {self.estimated_roi*100:.1f}% | Max Bid: €{self.max_bid:.0f}"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            'auction_url': self.auction.url,
            'category': self.category.value,
            'resale_value': self.resale_value,
            'max_bid': self.max_bid,
            'estimated_costs': self.estimated_costs,
            'estimated_roi': self.estimated_roi,
            'estimated_margin': self.estimated_margin,
            'notes': self.notes,
            'risk_factors': self.risk_factors,
            'detected_at': self.detected_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any], auction: Auction) -> 'Opportunity':
        """Create Opportunity from dictionary."""
        return cls(
            auction=auction,
            category=AuctionCategory(data['category']),
            resale_value=data['resale_value'],
            max_bid=data['max_bid'],
            estimated_costs=data['estimated_costs'],
            estimated_roi=data['estimated_roi'],
            estimated_margin=data['estimated_margin'],
            notes=data.get('notes', []),
            risk_factors=data.get('risk_factors', []),
            detected_at=datetime.fromisoformat(data.get('detected_at', datetime.now().isoformat())),
        )


@dataclass
class ValuationResult:
    """
    Result of a valuation for an auction.
    """
    category: AuctionCategory
    resale_value: float
    max_bid: float
    total_costs: float
    roi: float
    margin: float
    confidence: str  # high, medium, low
    notes: List[str] = field(default_factory=list)
    risk_factors: List[str] = field(default_factory=list)
    raw_valuation: Dict[str, Any] = field(default_factory=dict)

    def to_opportunity(self, auction: Auction) -> Opportunity:
        """Convert to Opportunity object."""
        return Opportunity(
            auction=auction,
            category=self.category,
            resale_value=self.resale_value,
            max_bid=self.max_bid,
            estimated_costs=self.total_costs,
            estimated_roi=self.roi,
            estimated_margin=self.margin,
            notes=self.notes,
            risk_factors=self.risk_factors,
        )


class AuctionCache:
    """
    Simple in-memory cache for auctions to avoid duplicates during a scan.
    """
    
    def __init__(self):
        self._cache: Dict[str, Auction] = {}
        self._seen_hashes: set = set()
    
    def add(self, auction: Auction) -> None:
        """Add auction to cache."""
        self._cache[auction.url] = auction
        self._seen_hashes.add(auction.auction_hash)
    
    def exists(self, url: str) -> bool:
        """Check if auction URL already in cache."""
        return url in self._cache
    
    def exists_by_hash(self, auction_hash: str) -> bool:
        """Check if auction hash already seen."""
        return auction_hash in self._seen_hashes
    
    def get(self, url: str) -> Optional[Auction]:
        """Get auction from cache."""
        return self._cache.get(url)
    
    def clear(self) -> None:
        """Clear cache."""
        self._cache.clear()
        self._seen_hashes.clear()
    
    def __len__(self) -> int:
        return len(self._cache)