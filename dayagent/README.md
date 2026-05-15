# AI Day Optimizer

An agentic AI system that generates optimized daily itineraries from natural language input. Built with Claude's tool-calling API, the agent autonomously searches venues, fetches live events, checks opening hours, analyzes real-time traffic and weather, and reasons over crowd patterns to build a time-aware schedule.

## How it works

Instead of a single LLM call, the system runs a 4-stage orchestration pipeline:

1. **Interpret** — Claude extracts structured constraints from the user's natural language input (fixed stops, time windows, preferences, budget)
2. **Prefetch** — weather forecast and live local events are fetched in parallel before the agent loop starts
3. **Agent loop** — Claude iteratively calls tools, grounding decisions in real-world data, until the plan is complete
4. **Validate + repair** — a Python constraint validation layer checks every output for time conflicts, travel feasibility violations, and budget breaches — sending structured repair feedback back to Claude if issues are found

## Tools the agent can call

| Tool | API | Purpose |
|------|-----|---------|
| `search_places` | Google Places API | Find venues near specific addresses |
| `get_place_details` | Google Places API | Live opening hours, price level |
| `get_directions` | Google Maps Directions API | Real travel time with traffic |
| `get_weather` | Open-Meteo (free) | Hourly forecast for the trip date |
| `get_busyness` | Heuristic reasoning | Crowd estimates for venues |
| `search_events` | Ticketmaster Discovery API | Live local events by date and city |

## Features

- Natural language input — describe your day in plain text
- Live event discovery — finds concerts, sports, shows happening that day
- Travel mode selection — driving, walking, transit, or bicycling
- Current location detection — auto-fills city via browser geolocation
- Crowd-aware scheduling — avoids peak hours, flags no-reservation restaurants
- Weather-aware planning — warns about rain, adjusts outdoor activity timing
- Constraint validation — catches time conflicts and travel feasibility issues in code
- Auto-repair loop — automatically fixes invalid outputs before returning results
- Swappable alternatives — flexible stops include multiple options to choose from
- Interactive map — numbered pins with route line and click-to-highlight

## Stack

**Backend:** Python, FastAPI, Anthropic SDK  
**Frontend:** React, TypeScript, Vite  
**APIs:** Claude API, Google Maps JS SDK, Google Places API, Google Maps Directions API, Ticketmaster Discovery API, Open-Meteo  

## Project structure

```
ai-day-optimize/
├── backend/
│   ├── main.py              # FastAPI app + full agent pipeline
│   │   ├── interpret_input()    # Stage 1: extract structured constraints
│   │   ├── prefetch_context()   # Stage 2: parallel weather + events fetch
│   │   ├── run_agent_loop()     # Stage 3: Claude tool-calling loop
│   │   ├── validate_and_repair() # Stage 4: constraint validation + repair
│   │   └── dispatch_tool()      # Tool router
│   ├── requirements.txt
│   └── .env.example
└── frontend/
    ├── src/
    │   ├── App.tsx              # Root component + split layout
    │   ├── App.css              # All styles
    │   ├── components/
    │   │   ├── PlanForm.tsx     # Input form with location detection
    │   │   ├── Timeline.tsx     # Itinerary sidebar with stop cards
    │   │   └── MapView.tsx      # Google Maps with numbered pins
    │   ├── hooks/
    │   │   └── usePlanDay.ts    # API call hook
    │   └── types/
    │       └── index.ts         # Shared TypeScript types
    └── .env.example
```

## Setup

### Requirements
- Python 3.10+
- Node.js 20+

### API keys needed
- **Anthropic API key** — [console.anthropic.com](https://console.anthropic.com)
- **Google API key** — [console.cloud.google.com](https://console.cloud.google.com) with these APIs enabled:
  - Places API
  - Maps JavaScript API
  - Directions API
  - Geocoding API
  - Time Zone API
- **Ticketmaster API key** — [developer.ticketmaster.com](https://developer.ticketmaster.com) (optional — app works without it)

### Backend

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env
# Fill in your API keys in .env
uvicorn main:app --reload
```

Backend runs at `http://localhost:8000`

### Frontend

```bash
cd frontend
npm install
cp .env.example .env.local
# Fill in VITE_GOOGLE_API_KEY in .env.local
npm run dev
```

Frontend runs at `http://localhost:5173`

## Example usage

**Input:**
> I want to go to a park in the morning, get Thai food for lunch (no reservation), and see whatever events are happening tonight

**Output:**
- Searches for parks near local events so stops are geographically clustered
- Checks Thai restaurant hours and flags peak dining times
- Pulls live events from Ticketmaster for the date
- Calculates real drive/walk time between each stop
- Returns an optimized schedule with warnings, reasoning, and an interactive map
