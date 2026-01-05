# LifeStats - Personal Food & Fitness Tracker

A PWA food tracking app with photo-based portion estimation.

## Quick Start

### 1. Get USDA API Key (Optional but Recommended)

1. Go to https://fdc.nal.usda.gov/api-key-signup.html
2. Fill out the form (takes 2 minutes)
3. You'll receive an API key via email
4. Add it to `backend/.env`:
   ```
   USDA_API_KEY=your-key-here
   ```

**Note:** App works with `DEMO_KEY` for testing, but has rate limits.

### 2. Start the Backend

```bash
cd backend
pip3 install -r requirements.txt
python3 app.py
```

Backend runs on http://localhost:5000

### 3. Access the App

- **Local:** http://localhost:5000
- **Phone (via tunnel):** Use localtunnel or ngrok

### 4. Install as PWA on iPhone

1. Open in Safari
2. Tap Share button (↑)
3. Scroll and tap "Add to Home Screen"
4. Tap "Add"

## Features

✅ Food logging with meal types (Breakfast/Lunch/Dinner/Snack)
✅ USDA FoodData Central integration for nutrition data
✅ PWA - works offline, installable on phone
✅ User ID tracking
✅ Local storage (easy to migrate to Supabase later)

## Project Structure

```
lifestats/
├── backend/
│   ├── app.py              # Flask server
│   ├── requirements.txt    # Python dependencies
│   └── .env               # API keys (gitignored)
├── frontend/
│   ├── index.html         # Main app
│   ├── storage.js         # Data layer
│   ├── manifest.json      # PWA manifest
│   └── sw.js             # Service worker
└── README.md
```

## API Endpoints

- `GET /api/search-food?q=chicken` - Search USDA database
- `GET /api/health` - Health check

## Tech Stack

- **Frontend:** Vanilla HTML/CSS/JS, PWA
- **Backend:** Python Flask
- **Database:** localStorage (migrating to Supabase soon)
- **APIs:** USDA FoodData Central, OpenAI Vision (planned)

## Roadmap

- [x] Basic food logging
- [x] USDA API integration
- [ ] Photo-based portion estimation (GPT Vision)
- [ ] Deploy to Vercel/Netlify
- [ ] Migrate to Supabase
- [ ] Barcode scanning