"""
Telegram alerts with inline buttons and photos.
"""
import logging
from typing import Optional, List
from datetime import datetime

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
    InputMediaPhoto,
)
from telegram.constants import ParseMode
from telegram.error import TelegramError
from telegram.ext import CallbackContext

from ..models import Opportunity, AuctionCategory


logger = logging.getLogger(__name__)


class TelegramAlerter:
    """
    Telegram alerter with inline buttons and photo support.
    """
    
    def __init__(
        self,
        token: str,
        chat_id: str,
        enabled: bool = True,
    ):
        """
        Initialize Telegram alerter.
        
        Args:
            token: Telegram bot token
            chat_id: Target chat ID
            enabled: Whether to send alerts
        """
        self.token = token
        self.chat_id = chat_id
        self.enabled = enabled
        
        # Will be initialized on first use
        self._bot = None
        self._application = None
    
    @property
    def bot(self):
        """Lazy initialization of bot."""
        if self._bot is None:
            from telegram import Bot
            self._bot = Bot(token=self.token)
        return self._bot
    
    def send_opportunity_alert(
        self,
        opportunity: Opportunity,
        config: dict,
    ) -> bool:
        """
        Send an opportunity alert to Telegram.
        
        Args:
            opportunity: The opportunity to alert about
            config: Configuration for formatting
            
        Returns:
            True if sent successfully
        """
        if not self.enabled:
            logger.debug("Telegram alerts disabled, skipping")
            return False
        
        try:
            auction = opportunity.auction
            
            # Format message
            message = self._format_message(opportunity, config)
            
            # Get images
            images = auction.images[:3]  # Limit to 3 images
            
            # Create inline keyboard
            keyboard = self._create_keyboard(opportunity)
            
            # Send message with or without photos
            if images:
                # Send first image with caption, then additional photos
                self._send_with_photos(message, images, keyboard)
            else:
                # Send text-only message
                self.bot.send_message(
                    chat_id=self.chat_id,
                    text=message,
                    parse_mode=ParseMode.HTML,
                    reply_markup=keyboard,
                    disable_web_page_preview=True,
                )
            
            logger.info(f"Sent alert for {auction.url}")
            return True
            
        except TelegramError as e:
            logger.error(f"Telegram error sending alert: {e}")
            return False
        except Exception as e:
            logger.error(f"Error sending Telegram alert: {type(e).__name__}: {e}")
            return False
    
    def _format_message(
        self,
        opportunity: Opportunity,
        config: dict,
    ) -> str:
        """Format the alert message."""
        auction = opportunity.auction
        cat = opportunity.category
        
        # Category emoji
        cat_emojis = {
            AuctionCategory.AUTO: '🚗',
            AuctionCategory.IMMOBILE: '🏠',
            AuctionCategory.GIOIELLO: '💎',
            AuctionCategory.OROLOGIO: '⌚',
            AuctionCategory.ALTRO: '📦',
        }
        emoji = cat_emojis.get(cat, '📦')
        
        # Build message
        lines = [
            f"<b>{emoji} OPPORTUNITÀ {cat.value.upper()} - {opportunity.estimated_roi*100:.0f}% ROI</b>",
            "",
            f"<b>🏷️ {auction.title[:100]}</b>",
            "",
        ]
        
        # Price info
        if auction.base_price:
            lines.append(f"💰 <b>Base:</b> €{auction.base_price:,.0f}")
        if auction.current_price:
            lines.append(f"💵 <b>Attuale:</b> €{auction.current_price:,.0f}")
        
        # End time
        if auction.end_datetime:
            mins_left = auction.minutes_to_end
            if mins_left is not None:
                lines.append(f"⏰ <b>Scade:</b> {auction.end_datetime.strftime('%d/%m %H:%M')} (tra {mins_left} min)")
        
        # Valuation
        lines.append("")
        lines.append(f"💎 <b>Val. Rivendita:</b> €{opportunity.resale_value:,.0f}")
        lines.append(f"🎯 <b>Max Bid:</b> €{opportunity.max_bid:,.0f}")
        lines.append(f"📈 <b>Margine:</b> €{opportunity.estimated_margin:,.0f}")
        
        # Confidence
        confidence_emoji = {'high': '✅', 'medium': '⚠️', 'low': '❌'}
        conf = opportunity.notes[-1] if opportunity.notes else 'medium'  # Simplified
        
        # Risk factors
        if opportunity.risk_factors:
            lines.append("")
            lines.append("⚠️ <b>Rischi:</b>")
            for rf in opportunity.risk_factors[:3]:
                lines.append(f"  • {rf}")
        
        # Notes
        if opportunity.notes:
            lines.append("")
            lines.append("📝 <b>Note:</b>")
            for note in opportunity.notes[:4]:
                lines.append(f"  • {note}")
        
        lines.append("")
        lines.append(f"<a href=\"{auction.url}\">🔗 Visualizza asta</a>")
        
        return '\n'.join(lines)
    
    def _create_keyboard(self, opportunity: Opportunity) -> InlineKeyboardMarkup:
        """Create inline keyboard with action buttons."""
        auction = opportunity.auction
        
        # Main action: View auction
        buttons = [
            [
                InlineKeyboardButton(
                    "🔗 Apri Asta",
                    url=auction.url,
                ),
            ],
        ]
        
        # Optional: Add to watchlist, share, etc.
        # These would require a callback handler to be functional
        extra_buttons = []
        
        # Auto valuation specific actions
        if opportunity.category == AuctionCategory.AUTO:
            extra_buttons.append(
                InlineKeyboardButton("🚗 Info Veicolo", callback_data=f"info_auto_{auction.url}")
            )
        elif opportunity.category == AuctionCategory.GIOIELLO:
            extra_buttons.append(
                InlineKeyboardButton("💎 Dettagli Oro", callback_data=f"info_gold_{auction.url}")
            )
        elif opportunity.category == AuctionCategory.IMMOBILE:
            extra_buttons.append(
                InlineKeyboardButton("🏠 Dettagli Immobile", callback_data=f"info_property_{auction.url}")
            )
        
        if extra_buttons:
            # Add in rows of 2
            for i in range(0, len(extra_buttons), 2):
                row = extra_buttons[i:i+2]
                buttons.append(row)
        
        return InlineKeyboardMarkup(buttons)
    
    def _send_with_photos(
        self,
        message: str,
        images: List[str],
        keyboard: InlineKeyboardMarkup,
    ) -> None:
        """Send message with photos."""
        # Send first image with caption
        try:
            self.bot.send_photo(
                chat_id=self.chat_id,
                photo=images[0],
                caption=message[:1024],  # Caption limited to 1024 chars
                parse_mode=ParseMode.HTML,
                reply_markup=keyboard,
            )
        except Exception as e:
            logger.warning(f"Could not send first photo: {e}")
            # Fall back to text-only
            self.bot.send_message(
                chat_id=self.chat_id,
                text=message,
                parse_mode=ParseMode.HTML,
                reply_markup=keyboard,
                disable_web_page_preview=True,
            )
            return
        
        # Send remaining images as album
        if len(images) > 1:
            media_group = []
            for img_url in images[1:]:
                try:
                    media_group.append(InputMediaPhoto(media=img_url))
                except Exception:
                    pass
            
            if media_group:
                try:
                    self.bot.send_media_group(
                        chat_id=self.chat_id,
                        media=media_group,
                    )
                except Exception as e:
                    logger.warning(f"Could not send media group: {e}")
    
    def send_status_message(self, message: str) -> bool:
        """Send a status message (for start/stop notifications)."""
        if not self.enabled:
            return False
        
        try:
            self.bot.send_message(
                chat_id=self.chat_id,
                text=message,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True,
            )
            return True
        except Exception as e:
            logger.error(f"Error sending status message: {e}")
            return False
    
    def test_connection(self) -> bool:
        """Test Telegram connection."""
        try:
            me = self.bot.get_me()
            logger.info(f"Connected to Telegram as {me.username}")
            return True
        except Exception as e:
            logger.error(f"Telegram connection test failed: {e}")
            return False


def create_alerter(
    token: Optional[str],
    chat_id: Optional[str],
    enabled: bool = True,
) -> Optional[TelegramAlerter]:
    """Create a Telegram alerter if credentials are provided."""
    if not token or not chat_id:
        logger.warning("Telegram credentials not provided, alerts disabled")
        return None
    
    return TelegramAlerter(token, chat_id, enabled)