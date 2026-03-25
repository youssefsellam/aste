"""
Scheduler and runner for the Fallco Aste Bot.
"""
import logging
import time
import random
import signal
import sys
from datetime import datetime
from typing import Optional, List
from pathlib import Path

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.interval import IntervalTrigger

from ..config import get_config
from ..models import Auction, Opportunity, AuctionCategory, AuctionCache
from ..storage.db import Database
from ..storage.migrations import create_tables
from ..fallco.client import FallcoClient
from ..fallco.parser import FallcoParser
from ..fallco.source import FallcoSources
from ..classify.classifier import AuctionClassifier
from ..valuation.jewelry import GoldSpotCache, JewelryValuator
from ..valuation.watches import WatchValuator
from ..valuation.cars import AutoValuator
from ..valuation.realestate import RealEstateValuator
from ..alerts.telegram import TelegramAlerter, create_alerter


logger = logging.getLogger(__name__)


class FallcoBot:
    """
    Main bot class that orchestrates all components.
    """
    
    def __init__(self, config_path: Optional[str] = None):
        """Initialize the bot."""
        # Load configuration
        self.config = get_config(config_path)
        
        # Setup logging
        from ..logging_setup import setup_logging
        setup_logging(
            level=self.config.log_level,
            log_file=self.config.log_file,
            console=self.config.log_console,
        )
        
        # Initialize components
        self._init_components()
        
        # State
        self._running = False
        self._scan_count = 0
        self._last_errors = []
        
        # Graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _init_components(self):
        """Initialize all components."""
        # Database
        db_path = self.config.db_path
        create_tables(db_path)
        self.db = Database(db_path)
        
        # HTTP Client
        self.client = FallcoClient(
            user_agent=self.config.user_agent,
            timeout=self.config.request_timeout,
            rate_limit_per_minute=self.config.rate_limit,
        )
        
        # Parser
        self.parser = FallcoParser()
        
        # Sources
        self.sources = FallcoSources(
            config={
                'sources': self.config.sources,
                'scanner': {
                    'max_pages_per_source': self.config.max_pages,
                }
            },
            client=self.client,
            parser=self.parser,
        )
        
        # Classifier
        self.classifier = AuctionClassifier(config={
            'watch_brands': self.config.watch_brands,
            'auto_tiers': self.config.auto_tiers,
        })
        
        # Gold cache for jewelry valuation
        self.gold_cache = GoldSpotCache(
            cache_minutes=self.config.gold_spot_cache_minutes,
            fallback_price=self.config.gold_spot_fallback,
        )
        
        # Valuators
        self.valuators = {
            AuctionCategory.GIOIELLO: JewelryValuator(self.gold_cache),
            AuctionCategory.OROLOGIO: WatchValuator({
                'watch_brands': self.config.watch_brands,
                'watch_values': self.config.watch_values,
            }),
            AuctionCategory.AUTO: AutoValuator({
                'auto_tiers': self.config.auto_tiers,
                'auto_values': self.config._config.get('auto_values', {}),
            }),
            AuctionCategory.IMMOBILE: RealEstateValuator({
                'omi_min_by_area': self.config.omi_min_by_area,
            }),
        }
        
        # Auction cache for dedup during scan
        self.auction_cache = AuctionCache()
        
        # Telegram alerter
        self.alerter = None
        if self.config.telegram_enabled:
            self.alerter = create_alerter(
                self.config.telegram_token,
                self.config.telegram_chat_id,
                enabled=True,
            )
            if self.alerter:
                self.alerter.test_connection()
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        logger.info("Received shutdown signal, stopping...")
        self._running = False
    
    def run(self):
        """Run the bot in a loop."""
        self._running = True
        
        logger.info("=" * 50)
        logger.info("Fallco Aste Bot starting...")
        logger.info(f"Scan interval: {self.config.scan_interval}s")
        logger.info(f"Horizon: {self.config.horizon_minutes} minutes")
        logger.info(f"ROI threshold: {self.config.roi_threshold*100}%")
        logger.info("=" * 50)
        
        # Send startup message
        if self.alerter:
            self.alerter.send_status_message(
                "<b>🤖 Fallco Aste Bot avviato</b>\n\n"
                f"Scansione ogni {self.config.scan_interval}s\n"
                f"Horizon: {self.config.horizon_minutes} min\n"
                f"ROI threshold: {self.config.roi_threshold*100}%"
            )
        
        # Main loop
        while self._running:
            try:
                self._run_scan()
                
                # Add small random jitter
                jitter = random.uniform(0, 5)
                time.sleep(self.config.scan_interval + jitter)
                
            except Exception as e:
                logger.error(f"Scan error: {type(e).__name__}: {e}")
                self._last_errors.append(str(e))
                if len(self._last_errors) > 10:
                    self._last_errors = self._last_errors[-10:]
                
                # Wait before retry
                time.sleep(10)
        
        logger.info("Bot stopped")
        
        # Send shutdown message
        if self.alerter:
            self.alerter.send_status_message(
                "<b>🤖 Fallco Aste Bot arrestato</b>\n\n"
                f"Scansioni effettuate: {self._scan_count}"
            )
        
        # Cleanup
        self.db.close()
        self.client.close()
    
    def _run_scan(self):
        """Run a single scan cycle."""
        self._scan_count += 1
        logger.info(f"[Scan #{self._scan_count}] Starting scan...")
        
        # Clear cache for new scan
        self.auction_cache.clear()
        
        # Fetch auctions from all sources
        try:
            auction_data_list = self.sources.fetch_all(
                horizon_minutes=self.config.horizon_minutes,
            )
        except Exception as e:
            logger.error(f"Error fetching auctions: {e}")
            return
        
        logger.info(f"Found {len(auction_data_list)} auctions in horizon")
        
        # Process each auction
        opportunities_found = 0
        alerts_sent = 0
        
        for data in auction_data_list:
            try:
                # Skip if already seen recently (dedup)
                if self.db.auction_exists(data['url']):
                    continue
                
                # Skip if already alerted recently
                if self.db.alert_exists(data['url'], hours=self.config.dedup_window_hours):
                    continue
                
                # Create Auction object
                auction = self._create_auction(data)
                
                # Classify
                category, confidence = self.classifier.classify(auction)
                auction.category = category
                
                logger.debug(f"Classified: {auction.title[:50]}... -> {category.value}")
                
                # Save to database
                self.db.save_auction(auction)
                
                # Try to value if profitable category
                if category not in [AuctionCategory.ALTRO, AuctionCategory.UNKNOWN]:
                    result = self._valuate(auction, category)
                    
                    if result and result.roi >= self.config.roi_threshold:
                        opportunity = result.to_opportunity(auction)
                        
                        # Send alert
                        if self.alerter:
                            if self.alerter.send_opportunity_alert(opportunity, self.config._config):
                                self.db.save_alert(opportunity)
                                alerts_sent += 1
                        
                        opportunities_found += 1
                        logger.info(f"💰 Opportunity: {opportunity.summary}")
                
            except Exception as e:
                logger.error(f"Error processing auction: {e}")
                continue
        
        logger.info(f"[Scan #{self._scan_count}] Complete: {len(auction_data_list)} auctions, "
                   f"{opportunities_found} opportunities, {alerts_sent} alerts")
        
        # Log stats
        stats = self.db.get_stats()
        logger.info(f"Stats: {stats}")
    
    def _create_auction(self, data: dict) -> Auction:
        """Create Auction object from raw data."""
        from dateutil import parser as date_parser
        
        # Parse end datetime
        end_dt = None
        if data.get('end_datetime'):
            if isinstance(data['end_datetime'], str):
                try:
                    end_dt = date_parser.parse(data['end_datetime'])
                except Exception:
                    pass
            else:
                end_dt = data['end_datetime']
        
        return Auction(
            url=data['url'],
            title=data.get('title', 'Unknown'),
            current_price=data.get('current_price'),
            base_price=data.get('base_price'),
            end_datetime=end_dt,
            location=data.get('location'),
            tribunal=data.get('tribunal'),
            procedure_number=data.get('procedure_number'),
            description=data.get('description'),
            images=data.get('images', []),
            raw_data={'raw_text': data.get('raw_text', '')},
        )
    
    def _valuate(self, auction: Auction, category: AuctionCategory):
        """Value an auction."""
        valuator = self.valuators.get(category)
        
        if not valuator:
            return None
        
        try:
            result = valuator.valuate(
                auction,
                category,
                self.config._config,
            )
            return result
        except Exception as e:
            logger.debug(f"Valuation error for {auction.url}: {e}")
            return None


def run_bot(config_path: Optional[str] = None):
    """Entry point to run the bot."""
    # Ensure data directory exists
    Path("data").mkdir(exist_ok=True)
    
    bot = FallcoBot(config_path)
    bot.run()


if __name__ == "__main__":
    run_bot()