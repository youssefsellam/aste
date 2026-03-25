"""
Cost calculation utilities.
"""
from typing import Dict, Any


def calculate_category_costs(
    category: str,
    config: Dict[str, Any],
    auction_data: Dict[str, Any] = None,
) -> Dict[str, float]:
    """
    Calculate total costs for a category.
    
    Args:
        category: Category name (auto, immobile, gioiello, orologio, altro)
        config: Full config dictionary
        auction_data: Optional auction data for adjustments
        
    Returns:
        Dictionary with cost breakdown
    """
    category_costs = config.get('costs', {}).get(category, config.get('costs', {}).get('altro', {}))
    
    costs = {
        'commission': 0.0,
        'trasporto': 0.0,
        'other': 0.0,
    }
    
    # Commission (percentage of final price)
    commission_pct = category_costs.get('commission_percent', 0.05)
    costs['commission'] = commission_pct
    
    # Transport costs
    costs['trasporto'] = category_costs.get('trasporto', 0)
    
    # Category-specific costs
    if category == 'auto':
        costs['passaggio'] = category_costs.get('passaggio_proprieta', 150)
        costs['ripristino'] = category_costs.get('ripristino', 300)
        costs['other'] += costs.get('passaggio', 0) + costs.get('ripristino', 0)
    
    elif category == 'immobile':
        costs['imposte'] = category_costs.get('imposte_registro', 0.02)
        costs['altre_spese'] = category_costs.get('altre_spese', 2000)
        costs['lavori'] = category_costs.get('lavori_stimati', 5000)
        costs['other'] += costs.get('altre_spese', 0) + costs.get('lavori', 0)
    
    elif category == 'gioiello':
        costs['certificazione'] = category_costs.get('certificazione', 50)
        costs['other'] += costs.get('certificazione', 0)
    
    elif category == 'orologio':
        costs['autenticazione'] = category_costs.get('autenticazione', 100)
        costs['restauro'] = category_costs.get('restauro', 200)
        costs['other'] += costs.get('autenticazione', 0) + costs.get('restauro', 0)
    
    return costs


def calculate_total_costs(
    category: str,
    config: Dict[str, Any],
    auction_data: Dict[str, Any] = None,
) -> float:
    """
    Calculate total fixed costs for a category.
    
    Args:
        category: Category name
        config: Full config dictionary
        auction_data: Optional auction data
        
    Returns:
        Total fixed costs in euros
    """
    costs = calculate_category_costs(category, config, auction_data)
    
    # Sum up all fixed costs (exclude percentage-based costs)
    total = costs.get('trasporto', 0) + costs.get('other', 0)
    
    return total


def estimate_commission(
    final_price: float,
    category: str,
    config: Dict[str, Any],
) -> float:
    """
    Estimate commission cost based on final price.
    
    Args:
        final_price: Final price of the auction
        category: Category name
        config: Full config dictionary
        
    Returns:
        Commission cost
    """
    category_costs = config.get('costs', {}).get(category, config.get('costs', {}).get('altro', {}))
    commission_pct = category_costs.get('commission_percent', 0.05)
    
    return final_price * commission_pct


def calculate_max_bid(
    resale_value: float,
    category: str,
    config: Dict[str, Any],
) -> float:
    """
    Calculate maximum bid based on resale value.
    
    Args:
        resale_value: Estimated resale value
        category: Category name
        config: Full config dictionary
        
    Returns:
        Maximum bid amount
    """
    category_costs = config.get('costs', {}).get(category, config.get('costs', {}).get('altro', {}))
    
    max_bid_percent = category_costs.get('max_bid_percent', 0.70)
    fixed_costs = calculate_total_costs(category, config)
    
    max_bid = (resale_value * max_bid_percent) - fixed_costs
    
    return max(0, max_bid)


def calculate_roi(
    resale_value: float,
    bid_amount: float,
    costs: float,
) -> float:
    """
    Calculate ROI percentage.
    
    Args:
        resale_value: Resale value
        bid_amount: Amount paid for the auction
        costs: Additional costs
        
    Returns:
        ROI as a decimal (e.g., 0.30 = 30%)
    """
    total_investment = bid_amount + costs
    
    if total_investment <= 0:
        return 0.0
    
    return (resale_value - total_investment) / total_investment


def calculate_margin(
    resale_value: float,
    bid_amount: float,
    costs: float,
) -> float:
    """
    Calculate margin in euros.
    
    Args:
        resale_value: Resale value
        bid_amount: Amount paid for the auction
        costs: Additional costs
        
    Returns:
        Margin in euros
    """
    return resale_value - (bid_amount + costs)