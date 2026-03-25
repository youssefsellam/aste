"""
Parser for Fallco Aste pages.
"""
import re
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple

from bs4 import BeautifulSoup
from dateutil import parser as date_parser
from datetime import datetime, timedelta


logger = logging.getLogger(__name__)


class FallcoParser:
    """
    Parser for Fallco Aste HTML pages.
    """
    
    # Patterns for countdown extraction
    COUNTDOWN_PATTERNS = [
        r'mancano\s*(?:ancora\s*)?(\d+)\s*giorni',
        r'mancano\s*(?:ancora\s*)?(\d+)\s*ore',
        r'mancano\s*(?:ancora\s*)?(\d+)\s*minuti',
        r'mancano\s*(?:ancora\s*)?(\d+)\s*min',
        r'scad(?:e|ono)\s*(?:tra\s*)?(\d+)\s*giorni',
        r'scad(?:e|ono)\s*(?:tra\s*)?(\d+)\s*ore',
        r'scad(?:e|ono)\s*(?:tra\s*)?(\d+)\s*minuti',
        r'scad(?:e|ono)\s*(?:tra\s*)?(\d+)\s*min',
        r'scadenza\s*:\s*(\d+)\s*giorni',
        r'scadenza\s*:\s*(\d+)\s*ore',
        r'(\d+)\s*g',
        r'(\d+)\s*h',
        r'(\d+)\s*min',
        r'(\d+):(\d+):(\d+)',  # HH:MM:SS format
    ]
    
    # Pattern for end date extraction
    END_DATE_PATTERNS = [
        r'Termine\s*vendita\s*[:\s]*(\d{1,2}/\d{1,2}/\d{2,4}\s*(?:h\s*)?(?:\d{1,2}:\d{2})?)',
        r'Scadenza\s*[:\s]*(\d{1,2}/\d{1,2}/\d{2,4}\s*(?:h\s*)?(?:\d{1,2}:\d{2})?)',
        r'scad(?:e|ono)\s*il\s*(\d{1,2}/\d{1,2}/\d{2,4})',
        r'Data\s*scadenza\s*[:\s]*(\d{1,2}/\d{1,2}/\d{2,4})',
    ]
    
    # Pattern for price extraction
    PRICE_PATTERNS = [
        r'Prezzo\s*base\s*[€£]?\s*:\s*[€£]?\s*([\d.]+)',
        r'Prezzo\s*[€£]?\s*:\s*[€£]?\s*([\d.]+)',
        r'€\s*([\d.]+)',
        r'([\d.]+)\s*€',
    ]
    
    # Pattern for current price
    CURRENT_PRICE_PATTERNS = [
        r'Offerta\s*attuale\s*[€£]?\s*:\s*[€£]?\s*([\d.]+)',
        r'Offerta\s*[€£]?\s*([\d.]+)',
        r'Prezzo\s*attuale\s*[€£]?\s*:\s*[€£]?\s*([\d.]+)',
    ]
    
    def __init__(self):
        """Initialize parser."""
        pass
    
    def parse_listing_page(self, html: str, source_url: str) -> List[Dict[str, Any]]:
        """
        Parse a listing page and extract auction items.
        
        Args:
            html: HTML content of the page
            source_url: URL of the page being parsed
            
        Returns:
            List of auction data dictionaries
        """
        auctions = []
        
        try:
            soup = BeautifulSoup(html, 'lxml')
            
            # Try multiple selectors for auction items
            items = self._extract_auction_items(soup)
            
            for item in items:
                auction_data = self._parse_auction_item(item)
                if auction_data:
                    auction_data['source_url'] = source_url
                    auctions.append(auction_data)
                    
        except Exception as e:
            logger.error(f"Error parsing listing page {source_url}: {e}")
        
        return auctions
    
    def _extract_auction_items(self, soup: BeautifulSoup) -> List[BeautifulSoup]:
        """Extract auction items from the page using various selectors."""
        # Try multiple selectors
        selectors = [
            'div.lotto', 
            'div.auction-item',
            'div.result-item',
            'article.lotto',
            'div.elenco-lotti div',
            'ul.lista-lotti li',
            '.results .item',
            'div[class*="lotto"]',
            'div[class*="asta"]',
        ]
        
        items = []
        for selector in selectors:
            items = soup.select(selector)
            if items:
                logger.debug(f"Found {len(items)} items with selector: {selector}")
                break
        
        # If no items found, try looking for links to auction details
        if not items:
            links = soup.find_all('a', href=True)
            auction_links = [a for a in links if '/vendita/' in a.get('href', '')]
            if auction_links:
                # Create pseudo-items from links
                for link in auction_links:
                    items.append(link)
        
        return items
    
    def _parse_auction_item(self, item) -> Optional[Dict[str, Any]]:
        """Parse a single auction item."""
        try:
            # Try to get title
            title = None
            title_selectors = ['h3', 'h2', 'a', '.titolo', '.title', 'title']
            for sel in title_selectors:
                el = item.select_one(sel)
                if el:
                    title = el.get_text(strip=True)
                    break
            
            if not title and item.name == 'a':
                title = item.get_text(strip=True)
            
            if not title:
                title = item.get_text(strip=True)[:100]
            
            # Get URL
            url = None
            if item.name == 'a':
                url = item.get('href')
            else:
                link = item.find('a', href=True)
                if link:
                    url = link.get('href')
            
            if not url:
                return None
            
            # Make absolute URL
            if url and not url.startswith('http'):
                url = f"https://www.fallcoaste.it{url}"
            
            # Get description text for further parsing
            item_text = item.get_text(separator=' ', strip=True)
            
            # Extract end datetime
            end_datetime = self._extract_end_datetime(item_text, item)
            
            # Extract prices
            base_price = self._extract_price(item_text, self.PRICE_PATTERNS)
            current_price = self._extract_price(item_text, self.CURRENT_PRICE_PATTERNS)
            
            # Extract tribunal/procedure
            tribunal = self._extract_tribunal(item_text)
            procedure = self._extract_procedure(item_text)
            
            # Extract images
            images = self._extract_images(item)
            
            # Extract location
            location = self._extract_location(item_text)
            
            return {
                'url': url,
                'title': title,
                'end_datetime': end_datetime,
                'base_price': base_price,
                'current_price': current_price,
                'tribunal': tribunal,
                'procedure_number': procedure,
                'location': location,
                'images': images,
                'raw_text': item_text[:500],
            }
            
        except Exception as e:
            logger.debug(f"Error parsing auction item: {e}")
            return None
    
    def _extract_end_datetime(self, text: str, item) -> Optional[datetime]:
        """Extract end datetime from item text or HTML."""
        # Try countdown first
        countdown_mins = self._parse_countdown(text)
        if countdown_mins is not None:
            return datetime.now() + timedelta(minutes=countdown_mins)
        
        # Try absolute date patterns
        for pattern in self.END_DATE_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    date_str = match.group(1)
                    # Handle various date formats
                    if 'h' in date_str.lower():
                        # Format: dd/mm/yyyy hh:mm
                        date_str = re.sub(r'h\s*', ' ', date_str)
                    
                    parsed = date_parser.parse(date_str, dayfirst=True)
                    return parsed
                except Exception:
                    pass
        
        # Try to find in HTML attributes
        if item:
            for attr in ['data-end', 'data-scadenza', 'data-endtime', 'data-expiry']:
                val = item.get(attr)
                if val:
                    try:
                        return datetime.fromisoformat(val)
                    except Exception:
                        pass
        
        return None
    
    def _parse_countdown(self, text: str) -> Optional[int]:
        """Parse countdown text to minutes."""
        text_lower = text.lower()
        
        # Check for days
        match = re.search(r'(\d+)\s*giorni?', text_lower)
        if match:
            return int(match.group(1)) * 24 * 60
        
        # Check for hours
        match = re.search(r'(\d+)\s*ore?', text_lower)
        if match:
            return int(match.group(1)) * 60
        
        # Check for minutes
        match = re.search(r'(\d+)\s*min(?:uti)?', text_lower)
        if match:
            return int(match.group(1))
        
        # Check for HH:MM:SS format
        match = re.search(r'(\d+):(\d+):(\d+)', text)
        if match:
            hours = int(match.group(1))
            mins = int(match.group(2))
            return hours * 60 + mins
        
        return None
    
    def _extract_price(self, text: str, patterns: List[str]) -> Optional[float]:
        """Extract price from text using patterns."""
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    # Remove thousand separators and get number
                    price_str = match.group(1).replace('.', '').replace(',', '.')
                    return float(price_str)
                except ValueError:
                    pass
        return None
    
    def _extract_tribunal(self, text: str) -> Optional[str]:
        """Extract tribunal from text."""
        match = re.search(r'Tribunale\s*di\s*([^\-]+)', text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
        return None
    
    def _extract_procedure(self, text: str) -> Optional[str]:
        """Extract procedure number from text."""
        match = re.search(r'Procedura\s*n[°.]?\s*(\d+/\d+)', text, re.IGNORECASE)
        if match:
            return match.group(1)
        return None
    
    def _extract_images(self, item) -> List[str]:
        """Extract image URLs from item."""
        images = []
        
        # Look for img tags
        imgs = item.find_all('img')
        for img in imgs:
            src = img.get('src') or img.get('data-src') or img.get('data-lazy')
            if src and not src.endswith('logo'):
                if not src.startswith('http'):
                    src = f"https://www.fallcoaste.it{src}"
                images.append(src)
        
        # Look for background images
        style = item.get('style', '')
        bg_match = re.search(r'url\(["\']?([^"\'()]+)["\']?\)', style)
        if bg_match:
            images.append(bg_match.group(1))
        
        return images[:5]  # Limit to 5 images
    
    def _extract_location(self, text: str) -> Optional[str]:
        """Extract location from text."""
        # Look for common location patterns
        patterns = [
            r'Ubicazione\s*[:\s]*([^\n]+)',
            r'Località\s*[:\s]*([^\n]+)',
            r'Localizzat[oa]\s*[:\s]*([^\n]+)',
            r'in\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s*\(?[A-Z]{2}\)?',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()[:100]
        
        return None
    
    def parse_detail_page(self, html: str, url: str) -> Optional[Dict[str, Any]]:
        """
        Parse a detail page for an auction.
        
        Args:
            html: HTML content of the detail page
            url: URL of the detail page
            
        Returns:
            Auction data dictionary
        """
        try:
            soup = BeautifulSoup(html, 'lxml')
            
            # Get title
            title = None
            for selector in ['h1', '.titolo', '.title', 'title']:
                el = soup.select_one(selector)
                if el:
                    title = el.get_text(strip=True)
                    break
            
            if not title:
                title = soup.title.string if soup.title else "Unknown"
            
            # Get description
            description = ""
            desc_selectors = ['.descrizione', '.description', '#descrizione', '.details']
            for sel in desc_selectors:
                el = soup.select_one(sel)
                if el:
                    description = el.get_text(separator=' ', strip=True)
                    break
            
            if not description:
                # Get all text content
                description = soup.get_text(separator=' ', strip=True)[:2000]
            
            # Get page text for extraction
            page_text = soup.get_text(separator=' ', strip=True)
            
            # Extract end datetime
            end_datetime = self._extract_end_datetime(page_text, soup)
            
            # Extract prices
            base_price = self._extract_price(page_text, self.PRICE_PATTERNS)
            current_price = self._extract_price(page_text, self.CURRENT_PRICE_PATTERNS)
            
            # Extract tribunal/procedure
            tribunal = self._extract_tribunal(page_text)
            procedure = self._extract_procedure(page_text)
            
            # Extract location
            location = self._extract_location(page_text)
            
            # Extract images
            images = []
            imgs = soup.find_all('img')
            for img in imgs:
                src = img.get('src') or img.get('data-src')
                if src and not src.endswith('logo') and 'fallcoaste' in src:
                    images.append(src)
            
            return {
                'url': url,
                'title': title,
                'description': description,
                'end_datetime': end_datetime,
                'base_price': base_price,
                'current_price': current_price,
                'tribunal': tribunal,
                'procedure_number': procedure,
                'location': location,
                'images': images[:10],
                'raw_text': page_text[:3000],
            }
            
        except Exception as e:
            logger.error(f"Error parsing detail page {url}: {e}")
            return None
    
    def extract_keyword_data(self, text: str) -> Dict[str, Any]:
        """
        Extract structured data from auction text for classification.
        
        Returns:
            Dictionary with extracted keywords and data
        """
        data = {
            'grams': None,
            'gold_title': None,
            'brand': None,
            'model': None,
            'year': None,
            'km': None,
            'fuel': None,
            'mq': None,
            'rooms': None,
            'has_box': False,
            'has_papers': False,
            'not_working': False,
            'no_keys': False,
            'administrative_hold': False,
        }
        
        # Gold/carat extraction
        match = re.search(r'titolo\s*(\d{3})', text, re.IGNORECASE)
        if match:
            data['gold_title'] = int(match.group(1))
        
        match = re.search(r'(\d{3})\s*KT', text, re.IGNORECASE)
        if match:
            data['gold_title'] = int(match.group(1))
        
        # Grams extraction - more specific patterns
        # Note: "gr." can appear BEFORE or AFTER the number
        # Also need to avoid matching "750 gr" where 750 is gold title
        gram_patterns = [
            r'gr\.?\s*(\d+[.,]?\d*)',  # "gr. 4,10" or "gr 4,10"
            r'grammi\s*:?\s*(\d+[.,]?\d*)',  # "grammi 4,10"
            r'peso\s*:?\s*(\d+[.,]?\d*)',  # "peso: 4,10"
        ]
        
        for pattern in gram_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                grams_str = match.group(1).replace(',', '.')
                try:
                    grams = float(grams_str)
                    # Only accept reasonable gram values (less than 10kg)
                    if grams < 10000:
                        data['grams'] = grams
                        break
                except ValueError:
                    pass
        
        # Year extraction
        match = re.search(r'anno\s*(\d{4})', text, re.IGNORECASE)
        if match:
            data['year'] = int(match.group(1))
        
        match = re.search(r'immatricolato.*?(\d{4})', text, re.IGNORECASE)
        if match:
            data['year'] = int(match.group(1))
        
        # KM extraction - use word boundaries
        km_patterns = [
            r'(\d{1,3}(?:\.\d{3})*)\s*km\b',  # "120.000 km" - with word boundary
            r'\bkm\s*:?\s*(\d+)',  # "km: 120000"
            r'chilometri\s*:?\s*(\d+)',  # "chilometri: 120000"
        ]
        
        for pattern in km_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                km_str = match.group(1).replace('.', '')
                try:
                    data['km'] = int(km_str)
                    break
                except ValueError:
                    pass
        
        # Fuel type
        for fuel in ['diesel', 'benzina', 'elettrico', 'ibrido', 'metano', 'gpl']:
            if fuel in text.lower():
                data['fuel'] = fuel
                break
        
        # Square meters
        match = re.search(r'(\d+)\s*mq', text, re.IGNORECASE)
        if match:
            data['mq'] = int(match.group(1))
        
        # Rooms
        match = re.search(r'(\d+)\s*(?:vani|locali|camere)', text, re.IGNORECASE)
        if match:
            data['rooms'] = int(match.group(1))
        
        # Condition flags
        data['has_box'] = 'box' in text.lower() or 'scatola' in text.lower()
        data['has_papers'] = 'documenti' in text.lower() or 'certificato' in text.lower()
        data['not_working'] = 'non funziona' in text.lower() or 'non marcia' in text.lower() or 'non funzionante' in text.lower()
        data['no_keys'] = 'senza chiavi' in text.lower() or 'chiavi mancanti' in text.lower()
        data['administrative_hold'] = 'fermo amministrativo' in text.lower() or 'precetto' in text.lower()
        
        return data