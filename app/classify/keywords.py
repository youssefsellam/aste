"""
Keyword definitions for auction classification.
"""
from typing import Dict, List, Set


# Keywords for jewelry/gold category
JEWELRY_KEYWORDS: Set[str] = {
    # Gold items
    'oro', 'oro giallo', 'oro bianco', 'oro rosa', 'oro 750', 'oro 585',
    'oro 18kt', 'oro 24kt', '18 kt', '24 kt',
    # Silver items
    'argento', 'argento 925', '800 argento',
    # Jewelry types
    'anello', 'fedi', 'fede', 'collana', 'braccialetto', 'bracciale',
    'orecchini', 'orologio', 'ciondolo', 'pendente', 'gemelli',
    'catena', 'cavigliera', 'piercing',
    # Precious stones
    'diamante', 'rubino', 'smeraldo', 'zaffiro', 'topazio',
    'perla', 'perle', 'ametista', 'citrino', 'acquamarina',
    # Materials
    'platino', 'titanio', 'acciaio', 'ceramica',
    # Gold related
    'giubbetto', 'lingotto', 'monile', ' preziosi', ' gioielleria',
}

# Keywords for watches category
WATCH_KEYWORDS: Set[str] = {
    # Watch brands - Luxury
    'rolex', 'patek', 'audemars', 'vacheron', 'lange', 'breguet',
    'iwc', 'jaeger', 'omega', 'cartier', 'tag heuer', 'longines',
    # Watch brands - High
    'tissot', 'zenith', 'hublot', 'panerai', 'bell & ross', 'francis',
    # Watch brands - Mid/Low
    'seiko', 'citizen', 'casio', 'swatch', 'fossil', 'movado',
    'guess', 'diesel', 'armani', 'burberry',
    # Watch terms
    'orologio', 'orologio automatico', 'orologio meccanico',
    'cronografo', 'cronometro', 'tourbillon', 'calibro',
    'movimento', 'quadrante', 'cassa', 'cinturino', 'bracciale',
    'fibbia', 'deployante', 'impermeabile', 'water resistant',
    ' GMT', ' dual time', 'chrono',
}

# Keywords for auto category
AUTO_KEYWORDS: Set[str] = {
    # Vehicle types
    'autovettura', 'automobile', 'auto', 'macchina', 'veicolo',
    'motociclo', 'motocicletta', 'moto', 'scooter', 'ciclomotore',
    'autocarro', 'furgone', 'camion', 'trattore', 'rimorchio',
    # Brands
    'fiat', 'mercedes', 'bmw', 'audi', 'volkswagen', 'opel',
    'renault', 'peugeot', 'citroen', 'ford', 'volvo', 'jaguar',
    'land rover', 'porsche', 'lexus', 'toyota', 'honda', 'nissan',
    'mazda', 'hyundai', 'kia', 'alfa romeo', 'lancia', 'chevrolet',
    'dacia', 'suzuki', 'daihatsu', 'jeep',
    # Fuel types
    'diesel', 'benzina', 'elettrico', 'ibrido', 'metano', 'gpl',
    # Auto terms
    'immatricolato', 'km', 'chilometri', 'targa', 'targato',
    'numero', 'telaio', 'motore', 'cambio', 'colore',
}

# Keywords for real estate category
REAL_ESTATE_KEYWORDS: Set[str] = {
    # Property types
    'appartamento', 'immobile', 'abitazione', 'alloggio',
    'villa', 'villino', 'casale', 'casa', 'palazzo',
    'ufficio', 'negozio', 'magazzino', 'laboratorio',
    'garage', 'box', 'cantina', 'soffitta', 'ripostiglio',
    'terreno', 'area', 'lotto', 'terreno edificabile',
    'capannone', 'stabilimento', 'hotel', 'albergo',
    # Real estate terms
    'mq', 'metri quadri', 'superficie', 'vani', 'locali',
    'camere', 'bagno', 'cucina', 'soggiorno', 'balcone',
    'terrazzo', 'giardino', 'posto auto', 'ascensore',
    'piano', 'seminterrato', 'cantina', 'solai', 'tetto',
    'proprietà', 'piena proprietà', 'nuda proprietà',
}

# High risk keywords (should reduce max bid)
HIGH_RISK_KEYWORDS: Set[str] = {
    # Not working / damaged
    'non funziona', 'non marcia', 'non funzionante', 'non avviabile',
    'danneggiato', 'rotto', 'difettoso', 'guasto', 'incompleto',
    # Missing documents/keys
    'senza chiavi', 'chiavi mancanti', 'documenti mancanti',
    'senza documenti', 'libretto mancante', 'certificato mancante',
    # Legal issues
    'fermo amministrativo', 'precetto', 'ipoteca', 'pignoramento',
    'trattenuta', 'debiti', 'oneri', 'gravami',
    # Other issues
    'da ripristinare', 'da sistemare', 'da completare',
    'stato grezzo', 'senza impianti', 'senza finiture',
}

# Positive keywords (increase confidence)
POSITIVE_KEYWORDS: Set[str] = {
    'garanzia', 'certificato', 'autenticato', 'originale',
    'con chiavi', 'con documenti', 'con libretto',
    'funzionante', 'marciante', 'perfetto stato',
    'ottimo stato', 'come nuovo', 'pari al nuovo',
    'completo', 'con box', 'con documenti',
}


def get_category_keywords(category: str) -> Set[str]:
    """Get keywords for a specific category."""
    category_map = {
        'gioiello': JEWELRY_KEYWORDS,
        'orologio': WATCH_KEYWORDS,
        'auto': AUTO_KEYWORDS,
        'immobile': REAL_ESTATE_KEYWORDS,
    }
    return category_map.get(category.lower(), set())


def get_all_category_keywords() -> Dict[str, Set[str]]:
    """Get all category keywords."""
    return {
        'gioiello': JEWELRY_KEYWORDS,
        'orologio': WATCH_KEYWORDS,
        'auto': AUTO_KEYWORDS,
        'immobile': REAL_ESTATE_KEYWORDS,
    }