# INvehi-DT v2.0 Advanced 🔍

**Indian Vehicle Registration OSINT Tool**
Created by **DigitalTracez**

---

## New in v2.0

| Feature | Description |
|---|---|
| 🗺 RC Decoder | Break down any RC number into state, RTO, series, number — no API needed |
| 📡 Live Monitor | Watch multiple vehicles continuously, get alerts when insurance is expiring |
| 📊 HTML Report | Generate a styled HTML report of all your lookups |
| 🗑 Watchlist | Add/remove vehicles to a persistent watchlist |
| 📋 Status Column | Every result shows VALID / EXPIRING SOON / EXPIRED with days remaining |
| ✓ Blacklist Check | Highlights blacklisted vehicles instantly |
| 💾 CSV Export | All results auto-append to a master CSV file |
| 📈 Query Stats | History shows total queries, success/fail counts |
| 🛡 System Info | Shows network status, public IP, cache stats |
| 🗂 Monthly Logs | Logs rotate monthly automatically |

---

## Installation

```bash
# Kali / Ubuntu
sudo apt update
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python3 invehidt.py
```

```bash
# Termux
pkg update && pkg install python git
pip install -r requirements.txt
python invehidt.py
```

---

## Usage

```bash
# Interactive menu (recommended)
python3 invehidt.py

# Single lookup
python3 invehidt.py --rc MH01AB1234

# Raw JSON output
python3 invehidt.py --rc MH01AB1234 --json

# Decode RC without API call
python3 invehidt.py --decode MH01AB1234

# Batch from file
python3 invehidt.py --batch rc_list.txt

# Force fresh (skip cache)
python3 invehidt.py --rc MH01AB1234 --no-cache

# Show version
python3 invehidt.py --version
```

---

## Menu Options

| Key | Feature |
|---|---|
| 1 | Single RC Lookup |
| 2 | Batch Lookup from file |
| 3 | Live Monitor (watchlist) |
| 4 | Generate HTML Report |
| 5 | Query History |
| 6 | Decode RC Number |
| 7 | Export all to CSV |
| 8 | System & Tool Info |
| 9 | Manage Watchlist |
| 0 | Exit |

---

## Data Storage

```
~/.invehidt/
├── cache/          ← SHA-256 keyed, 24h TTL
├── results/        ← JSON per lookup + all_results.csv
├── reports/        ← HTML reports
├── watchlist/      ← watchlist.json
└── logs/
    ├── invehidt_YYYYMM.log   ← monthly rotating log
    └── history.txt           ← last 200 queries
```

---

## Legal Disclaimer

Educational and ethical use only.
Unauthorized queries may violate **IT Act 2000 §43/66** (India).
