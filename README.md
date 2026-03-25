# Fallco Aste Bot 🤖

Bot per il monitoraggio delle aste giudiziarie su [Fallco Aste](https://www.fallcoaste.it/) e la segnalazione di opportunità di arbitraggio in tempo reale.

## ⚡️ Quick Start

```bash
# 1. Clona il repository
git clone https://github.com/your-repo/fallco-aste-bot.git
cd fallco-aste-bot

# 2. Crea e attiva l'ambiente virtuale
python3 -m venv venv
source venv/bin/activate

# 3. Installa le dipendenze
pip install -r requirements.txt

# 4. Copia e modifica la configurazione
cp config.yaml.example config.yaml
cp .env.example .env

# 5. Modifica config.yaml e .env con le tue impostazioni

# 6. Avvia il bot
python -m app.main
```

## 📋 Requisiti

- Python 3.8+
- Linux (VPS 24/7)
- Token Telegram Bot (vedi configurazione)

## 📁 Struttura del Progetto

```
fallco-aste-bot/
├── app/
│   ├── main.py                 # Entry point
│   ├── config.py               # Caricamento configurazione
│   ├── logging_setup.py        # Setup logging
│   ├── models.py               # Modelli dati
│   ├── fallco/
│   │   ├── client.py           # HTTP client con rate limit
│   │   ├── parser.py           # Parser HTML Fallco
│   │   └── source.py           # Gestione fonti dati
│   ├── classify/
│   │   ├── classifier.py       # Classificazione aste
│   │   └── keywords.py         # Keyword per categorie
│   ├── valuation/
│   │   ├── base.py             # Interfaccia valutazione
│   │   ├── jewelry.py          # Valutazione gioielli
│   │   ├── watches.py          # Valutazione orologi
│   │   ├── cars.py            # Valutazione auto
│   │   ├── realestate.py       # Valutazione immobili
│   │   └── costs.py            # Calcolo costi
│   ├── storage/
│   │   ├── db.py               # Database SQLite
│   │   └── migrations.py       # Creazione tabelle
│   ├── alerts/
│   │   └── telegram.py         # Notifiche Telegram
│   └── scheduler/
│       └── runner.py           # Loop principale
├── tests/
│   ├── test_parser.py
│   ├── test_classifier.py
│   └── test_valuation.py
├── data/                       # Database SQLite
├── config.yaml.example         # Template configurazione
├── .env.example                # Template variabili ambiente
├── requirements.txt
└── README.md
```

## ⚙️ Configurazione

### 1. config.yaml

Copia `config.yaml.example` in `config.yaml` e modifica:

```yaml
# Scanner
scanner:
  scan_interval_seconds: 60       # Intervallo tra scansioni
  horizon_minutes: 60            # Minuti prima della scadenza
  max_pages_per_source: 5        # Pagine massime per fonte
  rate_limit_per_minute: 30      # Rate limit richieste

# Fonti da monitorare
sources:
  - name: "ricerca"
    url: "https://www.fallcoaste.it/ricerca.html"
    enabled: true
  - name: "autovetture"
    url: "https://www.fallcoaste.it/categoria/autovetture-594.html"
    enabled: true
  # ... altre fonti

# Opportunità
opportunity:
  roi_threshold: 0.30            # Soglia ROI (30%)
  dedup_window_hours: 24         # Non alertare stessa asta entro X ore

# Costi per categoria
costs:
  auto:
    commission_percent: 0.05
    trasporto: 200
    passaggio_proprieta: 150
    ripristino: 300
    haircut: 0.15               # Sconto prudenziale
    max_bid_percent: 0.70       # % del valore rivendita
    
  # ... altre categorie (immobile, gioiello, orologio)

# Parametri oro
gold_spot:
  cache_minutes: 10
  fallback_price_eur_per_gram: 72.00

# Brand orologi
watch_brands:
  luxury:
    - "Rolex"
    - "Patek Philippe"
  # ...

# Valori base orologi (€)
watch_values:
  luxury: 5000
  high: 1500
  
# Tier auto
auto_tiers:
  luxury:
    - "Mercedes"
    - "BMW"
  # ...

# Valori auto (€) [nuovo, medio, vecchio]
auto_values:
  luxury: [40000, 25000, 15000]
  # ...

# Valori OMI (€/mq)
omi_min_by_area:
  Milano:
    centro: 4500
    semicentro: 3500
  # ...
```

### 2. .env

Copia `.env.example` in `.env`:

```env
# Telegram (OBBLIGATORIO per ricevere alert)
TELEGRAM_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
TELEGRAM_CHAT_ID=123456789

# Opzionale
DEBUG=false
```

### Ottenere Token Telegram

1. Apri Telegram e cerca `@BotFather`
2. Invia `/newbot` e segui le istruzioni
3. Copia il token ricevuto
4. Cerca `@userinfobot` per ottenere il tuo Chat ID

## 🚀 Esecuzione

### Modalità normale
```bash
python -m app.main
```

### Con config personalizzato
```bash
python -m app.main -c config.yaml
```

### In background (VPS)
```bash
# Con nohup
nohup python -m app.main > bot.log 2>&1 &

# Con systemd (consigliato per produzione)
# Crea /etc/systemd/system/fallco-bot.service
```

## 📱 Esempio di Messaggio Telegram

Il bot invia messaggi strutturati con:

```
💎 OPPORTUNITÀ AUTO - 35% ROI

🏷️ AUTOVETTURA MERCEDES C220 CDI ANNO 2019

💰 Base: €15,000
💵 Attuale: €12,500

⏰ Scade: 25/03/2026 15:30 (tra 45 min)

💎 Val. Rivendita: €22,000
🎯 Max Bid: €13,500
📈 Margine: €6,500

🔗 Visualizza asta

[🔗 Apri Asta] [🚗 Info Veicolo]
```

Con foto dell'asta se disponibili.

## 🧪 Test

```bash
# Esegui tutti i test
pytest

# Test specifici
pytest tests/test_parser.py
pytest tests/test_classifier.py
pytest tests/test_valuation.py

# Con coverage
pytest --cov=app tests/
```

## ⚠️ Regole e Limitazioni

- ❌ **VIETATO**: Auto-bidding, bypass login/captcha, scraping aggressivo
- ✅ **CONSIGLIATO**: Lettura pagine pubbliche, analisi, notifiche
- ✅ Rispetta rate limit configurato
- ✅ User-Agent appropriato
- ✅ Dedup delle aste per evitare spam

## 🔧 Manutenzione

### Backup database
```bash
cp data/fallco_bot.db data/fallco_bot_$(date +%Y%m%d).db
```

### Pulizia vecchi record
```bash
# Dal codice
python -c "from app.storage.db import Database; db = Database(); db.cleanup_old_records(30)"
```

### Monitoraggio
```bash
# Log
tail -f bot.log

# Statistiche
python -c "from app.storage.db import Database; print(Database().get_stats())"
```

## 📝 Licenza

MIT License - vedi LICENSE file

## 🙏 Ringraziamenti

- [Fallco Aste](https://www.fallcoaste.it/) per la piattaforma
- Comunità open source per i tool utilizzati
