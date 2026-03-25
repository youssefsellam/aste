"""
Configuration loader - loads .env and config.yaml with validation.
"""
import os
import logging
from pathlib import Path
from typing import Any, Dict, Optional
from dotenv import load_dotenv
import yaml


logger = logging.getLogger(__name__)


class Config:
    """Configuration manager for Fallco Aste Bot."""

    def __init__(self, config_path: Optional[str] = None, env_path: Optional[str] = None):
        # Load .env file
        if env_path:
            load_dotenv(env_path)
        else:
            load_dotenv()

        # Set base paths
        self.base_dir = Path(__file__).parent.parent
        self.config_path = config_path or os.getenv('CONFIG_PATH', 'config.yaml')
        self.db_path = os.getenv('DB_PATH', 'data/fallco_bot.db')

        # Load config
        self._config = self._load_config()

        # Validate required fields
        self._validate()

    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from YAML file."""
        config_file = self.base_dir / self.config_path

        if not config_file.exists():
            logger.warning(f"Config file not found: {config_file}")
            return {}

        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                logger.info(f"Loaded configuration from {config_file}")
                return config or {}
        except yaml.YAMLError as e:
            logger.error(f"Error parsing config file: {e}")
            return {}

    def _validate(self) -> None:
        """Validate required configuration fields."""
        required_sections = ['scanner', 'sources', 'opportunity', 'costs']

        for section in required_sections:
            if section not in self._config:
                logger.warning(f"Missing config section: {section}")

        # Validate scanner
        if 'scanner' in self._config:
            scanner = self._config['scanner']
            if 'scan_interval_seconds' not in scanner:
                scanner['scan_interval_seconds'] = 60
            if 'horizon_minutes' not in scanner:
                scanner['horizon_minutes'] = 60

        # Validate opportunity
        if 'opportunity' in self._config:
            opp = self._config['opportunity']
            if 'roi_threshold' not in opp:
                opp['roi_threshold'] = 0.30
            if 'dedup_window_hours' not in opp:
                opp['dedup_window_hours'] = 24

        # Validate costs
        if 'costs' not in self._config:
            self._config['costs'] = self._get_default_costs()

        # Validate sources
        if 'sources' not in self._config:
            self._config['sources'] = []

        # Validate gold_spot
        if 'gold_spot' not in self._config:
            self._config['gold_spot'] = {
                'cache_minutes': 10,
                'fallback_price_eur_per_gram': 72.00
            }

    def _get_default_costs(self) -> Dict[str, Any]:
        """Return default costs if not configured."""
        return {
            'auto': {
                'commission_percent': 0.05,
                'trasporto': 200,
                'passaggio_proprieta': 150,
                'ripristino': 300,
                'other_costs': 100,
                'haircut': 0.15,
                'max_bid_percent': 0.70
            },
            'immobile': {
                'commission_percent': 0.05,
                'imposte_registro': 0.02,
                'altre_spese': 2000,
            },
            'gioiello': {
                'commission_percent': 0.05,
                'trasporto': 15,
                'certificazione': 50,
                'haircut': 0.20,
                'max_bid_percent': 0.80
            },
            'orologio': {
                'commission_percent': 0.05,
                'trasporto': 30,
                'autenticazione': 100,
                'restauro': 200,
                'haircut': 0.15,
                'max_bid_percent': 0.70
            },
            'altro': {
                'commission_percent': 0.05,
                'trasporto': 50,
                'haircut': 0.25,
                'max_bid_percent': 0.60
            }
        }

    # Scanner settings
    @property
    def scan_interval(self) -> int:
        return self._config.get('scanner', {}).get('scan_interval_seconds', 60)

    @property
    def horizon_minutes(self) -> int:
        return self._config.get('scanner', {}).get('horizon_minutes', 60)

    @property
    def max_pages(self) -> int:
        return self._config.get('scanner', {}).get('max_pages_per_source', 5)

    @property
    def rate_limit(self) -> int:
        return self._config.get('scanner', {}).get('rate_limit_per_minute', 30)

    @property
    def request_timeout(self) -> int:
        return self._config.get('scanner', {}).get('request_timeout_seconds', 30)

    @property
    def user_agent(self) -> str:
        return self._config.get('scanner', {}).get(
            'user_agent',
            'FallcoAsteBot/1.0 (Monitoring Bot)'
        )

    # Opportunity settings
    @property
    def roi_threshold(self) -> float:
        return self._config.get('opportunity', {}).get('roi_threshold', 0.30)

    @property
    def min_resale_value(self) -> float:
        return self._config.get('opportunity', {}).get('min_resale_value', 50)

    @property
    def dedup_window_hours(self) -> int:
        return self._config.get('opportunity', {}).get('dedup_window_hours', 24)

    # Sources
    @property
    def sources(self) -> list:
        return self._config.get('sources', [])

    # Costs
    @property
    def costs(self) -> Dict[str, Any]:
        return self._config.get('costs', {})

    def get_category_costs(self, category: str) -> Dict[str, Any]:
        """Get costs for a specific category."""
        return self.costs.get(category, self.costs.get('altro', {}))

    # Gold spot
    @property
    def gold_spot_cache_minutes(self) -> int:
        return self._config.get('gold_spot', {}).get('cache_minutes', 10)

    @property
    def gold_spot_fallback(self) -> float:
        return self._config.get('gold_spot', {}).get('fallback_price_eur_per_gram', 72.00)

    # Watch brands
    @property
    def watch_brands(self) -> Dict[str, list]:
        return self._config.get('watch_brands', {
            'luxury': ['Rolex', 'Patek Philippe'],
            'high': ['Cartier', 'Tag Heuer'],
            'mid': ['Seiko', 'Citizen'],
            'low': ['Generic']
        })

    @property
    def watch_values(self) -> Dict[str, int]:
        return self._config.get('watch_values', {
            'luxury': 5000,
            'high': 1500,
            'mid': 300,
            'low': 100
        })

    # Auto tiers
    @property
    def auto_tiers(self) -> Dict[str, list]:
        return self._config.get('auto_tiers', {
            'luxury': ['Mercedes', 'BMW', 'Audi'],
            'premium': ['Volkswagen', 'Volvo', 'Peugeot'],
            'budget': ['Fiat', 'Lancia', 'Ford']
        })

    # OMI values
    @property
    def omi_min_by_area(self) -> Dict[str, Any]:
        return self._config.get('omi_min_by_area', {'DEFAULT': {'DEFAULT': 1200}})

    # Telegram
    @property
    def telegram_token(self) -> Optional[str]:
        return os.getenv('TELEGRAM_TOKEN')

    @property
    def telegram_chat_id(self) -> Optional[str]:
        return os.getenv('TELEGRAM_CHAT_ID')

    @property
    def telegram_enabled(self) -> bool:
        return bool(self.telegram_token and self.telegram_chat_id)

    # Logging
    @property
    def log_level(self) -> str:
        return self._config.get('logging', {}).get('level', 'INFO')

    @property
    def log_file(self) -> str:
        return self._config.get('logging', {}).get('file', 'fallco_bot.log')

    @property
    def log_console(self) -> bool:
        return self._config.get('logging', {}).get('console', True)


# Global config instance
_config_instance: Optional[Config] = None


def get_config(config_path: Optional[str] = None, env_path: Optional[str] = None) -> Config:
    """Get or create global config instance."""
    global _config_instance
    if _config_instance is None:
        _config_instance = Config(config_path, env_path)
    return _config_instance


def reload_config(config_path: Optional[str] = None, env_path: Optional[str] = None) -> Config:
    """Force reload config."""
    global _config_instance
    _config_instance = Config(config_path, env_path)
    return _config_instance