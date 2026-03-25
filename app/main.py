#!/usr/bin/env python3
"""
Fallco Aste Bot - Main Entry Point

Monitora le aste su Fallco Aste e segnala opportunità di arbitraggio.
"""
import sys
import argparse
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.scheduler.runner import run_bot


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Fallco Aste Bot - Monitor aste e segnala opportunità"
    )
    parser.add_argument(
        '-c', '--config',
        default='config.yaml',
        help='Path to config file (default: config.yaml)'
    )
    parser.add_argument(
        '--version',
        action='version',
        version='Fallco Aste Bot v1.0.0'
    )
    
    args = parser.parse_args()
    
    # Run the bot
    run_bot(args.config)


if __name__ == "__main__":
    main()