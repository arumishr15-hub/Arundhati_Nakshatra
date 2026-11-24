# Arundhati Nakshatra — Vedic Astrology App

Works on **K.N. Rao principles**: Parashari functional lordship, promise in D1 confirmed in the relevant varga (D9 / D10 / D7), Jaimini karakas, and timing by the triple check of Vimshottari dasha + Jaimini Chara Dasha + double transit of Jupiter and Saturn.

Four agents working on one kundali:

| # | Agent | What it does |
|---|-------|--------------|
| 1 | **Kundali Agent** | Janam Patrika (D1), Navamsha (D9), Dashamsha (D10), Saptamsha (D7), Chandra Kundali, Bhava Chalit, Vimshottari and Chara Dasha with antardashas, functional benefics/malefics, chara karakas, Arudha Lagna, Upapada, double transit timeline |
| 2 | **Analyst Agent** | Full reasoned report of the Lagna chart and the Navamsha chart (every graha, house, aspect, conjunction, yoga/dosha, dasha timing) + "Ask about this chart" follow-ups |
| 3 | **Booking Agent** | Chats with the client and books a kundali consultation with you, using your profile, services, fees and working hours |
| 4 | **Note-Taker Agent** | Reads all reports and gives the crux, current period, key dates and remedies (mantra, daan, vrat, gemstone guidance) |

## Run it

```bash
./start.sh            # macOS / Linux (first run installs packages)
```
Then open http://localhost:8000.

Manual way:
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # paste your ANTHROPIC_API_KEY
python backend/main.py
```

Agents 2–4 need an Anthropic API key in `.env` (get one at console.anthropic.com).
Without it, the app runs in a basic offline mode with rule-based text.

## Use it on your iPhone
Put it online for free (Render + Neon) and add it to your iPhone home screen — see **DEPLOY.md**.
Online, the app asks for a password (`APP_PASSWORD`) and stores data in the database (`DATABASE_URL`).

## First steps
1. Open **My Profile** and fill in your name, bio, services, fees and working hours.
2. On **New Kundali**, enter Name, DOB, TOB, POB and generate.
3. On the Analysis tab, generate the D1 report, then the D9 report. Then create Notes & Remedies.

## Where data is saved
Everything is in the `data/` folder of this project:
```
data/astrologer_profile.json
data/appointments.json
data/profiles/<name-id>/birth_details.json, kundali.json, report_d1.md, report_d9.md, notes.md, chat.json
```

## Calculation notes
**K.N. Rao layer** (`backend/knrao.py`)
- Functional nature by Laghu Parashari (trikona lords benefic, 3/6/11 malefic, kendradhipati dosha, yogakaraka)
- 7 chara karakas (Rahu excluded), Karakamsha, Arudha Lagna, Upapada, rashi drishti
- Chara Dasha: starts from Lagna; direction from the 9th sign from Lagna (Ar/Ta/Ge/Li/Sc/Sg direct, others reverse); years = count to the lord − 1, own sign 12; **no ±1 for exalted/debilitated lords**; stronger co-lord for Scorpio/Aquarius; 12 equal antardashas starting from the next sign, MD sign last; second cycle = 12 − first-cycle years
- Double transit: houses influenced by both Jupiter and Saturn (occupation or Vedic aspect) from Lagna and Moon, month by month for 3 years

**General**
- Sidereal zodiac, **Lahiri (Chitrapaksha)** ayanamsa, Swiss Ephemeris (built-in Moshier ephemeris, about 1 arc-second accuracy, no data files needed)
- Whole-sign houses for D1/D9/Chandra; **Sripati** cusps for Bhava Chalit
- Mean node for Rahu/Ketu; Vimshottari year = 365.25 days
- Place search uses free, no-key APIs: Open-Meteo Geocoding, Photon and Nominatim (OpenStreetMap), queried together. If the internet is down it falls back to an offline database of ~34,000 cities. You can also type coordinates like `25.32, 82.97`. Check which APIs are reachable at http://localhost:8000/api/geocode/health
