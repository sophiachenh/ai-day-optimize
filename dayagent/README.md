# DayAgent 🗺

AI-powered daily itinerary planner. Give it a list of things you want to do — it searches for venues, checks opening hours, avoids crowds, calculates routes, and builds an optimized schedule.

## How it works (the agentic part)

The backend runs a Claude agent in a tool-calling loop. Claude has access to 5 tools:

| Tool | API | Cost |
|------|-----|------|
| `search_places` | Google Places Text Search | ~$0/mo (free credit) |
| `get_place_details` | Google Places Details | ~$0/mo (free credit) |
| `get_directions` | Google Maps Directions | ~$0/mo (free credit) |
| `get_weather` | Open-Meteo | Free, no key needed |
| `get_busyness` | BestTime.app (optional) | Free tier: 50/mo |

Claude reasons over results, re-calls tools when it hits constraints (e.g. "restaurant closes at 9pm, concert ends at 10pm — adjusting..."), and produces a structured JSON itinerary.

## Stack
- **Backend**: Python + FastAPI + Anthropic SDK
- **Frontend**: React + TypeScript + Vite
- **Maps**: Google Maps JS SDK

---

## Setup

### 1. Get API keys

**Anthropic API key**
- https://console.anthropic.com → API Keys → Create key

**Google API key**
- https://console.cloud.google.com → APIs & Services → Credentials → Create API key
- Enable these APIs on your project:
  - Places API
  - Maps JavaScript API
  - Directions API

**BestTime.app (optional)**
- https://besttime.app → Sign up → free tier gives 50 forecast calls/month
- If you skip this, the agent uses heuristic reasoning for busyness (still works great)

---

### 2. Backend

```bash
cd backend

# Install dependencies
pip install -r requirements.txt

# Set up env
cp .env.example .env
# Edit .env with your keys

# Run
source .env && uvicorn main:app --reload
# OR with dotenv:
# pip install python-dotenv
# Then add: from dotenv import load_dotenv; load_dotenv() at top of main.py
```

Backend runs at http://localhost:8000
API docs at http://localhost:8000/docs

---

### 3. Frontend

```bash
cd frontend

# Install
npm install

# Set up env
cp .env.example .env.local
# Edit .env.local with your Google API key

# Run
npm run dev
```

Frontend runs at http://localhost:5173

---

## Usage

1. Enter a city (e.g. "Seattle, WA")
2. Pick a date
3. Describe what you want to do in plain text:
   > "Go to a park in the morning, get Thai food for lunch (no reservation), see live music in the evening, stop by a grocery store"
4. Hit "Plan my day" — the agent runs for ~15-30 seconds
5. Get an optimized itinerary with a map, times, travel gaps, and the agent's reasoning

---

## Project structure

```
dayagent/
├── backend/
│   ├── main.py          # FastAPI app + Claude agent loop + all 5 tools
│   ├── requirements.txt
│   └── .env.example
└── frontend/
    ├── src/
    │   ├── App.tsx           # Root component + layout
    │   ├── App.css           # All styles
    │   ├── components/
    │   │   ├── PlanForm.tsx  # Input form
    │   │   ├── Timeline.tsx  # Itinerary sidebar
    │   │   └── MapView.tsx   # Google Maps with stop markers
    │   ├── hooks/
    │   │   └── usePlanDay.ts # API call hook
    │   └── types/
    │       └── index.ts      # Shared TypeScript types
    └── .env.example
```

---

## Resume talking points

- **Agentic loop**: Claude runs multiple tool-call iterations, not just one API call. It re-plans when constraints aren't met.
- **Multi-source reasoning**: Combines 4 different APIs + heuristic fallback into a coherent plan.
- **Structured output**: Agent returns typed JSON parsed into React components.
- **Real production stack**: FastAPI + React + TypeScript — same stack as the job description.
- **Tool design**: Each tool has a typed input schema Claude uses to decide when/how to call it.
