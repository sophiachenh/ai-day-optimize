import os
import json
import httpx
import time
import re
from datetime import datetime, timedelta
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, field_validator
from typing import Optional
import anthropic
import zoneinfo

app = FastAPI(title="DayAgent API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

anthropic_client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
GOOGLE_API_KEY = os.environ["GOOGLE_API_KEY"]
TICKETMASTER_API_KEY = os.environ.get("TICKETMASTER_API_KEY", "")
BESTTIME_API_KEY = os.environ.get("BESTTIME_API_KEY", "")


# ============================================================
# MODELS
# ============================================================

class PlanRequest(BaseModel):
    message: str
    location: str
    date: str
    travel_mode: str = "driving"
    budget: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None


class StopOption(BaseModel):
    name: str
    address: str
    place_id: str
    lat: float
    lng: float
    notes: str
    category: str
    price_level: Optional[int] = None
    rating: Optional[float] = None
    url: Optional[str] = None


class Stop(BaseModel):
    name: str
    address: str
    place_id: str
    lat: float
    lng: float
    arrival_time: str
    duration_minutes: int
    travel_time_from_prev: Optional[int] = None
    notes: str
    category: str
    price_level: Optional[int] = None
    rating: Optional[float] = None
    is_flexible: bool = False
    options: Optional[list[StopOption]] = None
    selected_option_index: int = 0

    @field_validator("category")
    @classmethod
    def validate_category(cls, v):
        valid = {"restaurant", "park", "entertainment", "shopping", "other"}
        return v if v in valid else "other"


class ItineraryResponse(BaseModel):
    stops: list[Stop]
    summary: str
    reasoning: str
    warnings: list[str]
    travel_mode: str = "driving"
    validation_notes: list[str] = []


# ============================================================
# CONSTRAINT VALIDATION
# ============================================================

class ConstraintViolation(BaseModel):
    stop_index: Optional[int]
    field: str
    message: str
    severity: str


def validate_constraints(stops: list[dict], req: PlanRequest) -> list[ConstraintViolation]:
    violations = []
    BUDGET_MAX = {"low": 1, "medium": 2, "high": 4}

    def parse_time(t: str) -> int:
        try:
            h, m = map(int, t.split(":"))
            return h * 60 + m
        except Exception:
            return -1

    prev_end = None
    prev_lat = prev_lng = prev_name = None

    for i, stop in enumerate(stops):
        name = stop.get("name", f"Stop {i+1}")
        arrival = stop.get("arrival_time", "")
        duration = stop.get("duration_minutes", 0)
        travel = stop.get("travel_time_from_prev")
        lat = stop.get("lat", 0)
        lng = stop.get("lng", 0)
        arrival_min = parse_time(arrival)

        # Required fields
        for field in ["name", "address", "place_id", "lat", "lng", "arrival_time", "duration_minutes", "notes", "category"]:
            if not stop.get(field) and stop.get(field) != 0:
                violations.append(ConstraintViolation(stop_index=i, field=field, message=f"'{name}' missing field: {field}", severity="error"))

        # Start time
        if req.start_time and i == 0:
            start_min = parse_time(req.start_time)
            if arrival_min > 0 and arrival_min < start_min:
                violations.append(ConstraintViolation(stop_index=i, field="arrival_time", message=f"'{name}' starts at {arrival} before requested start {req.start_time}", severity="error"))

        # End time
        if req.end_time and arrival_min > 0:
            end_min = parse_time(req.end_time)
            stop_end = arrival_min + duration
            if stop_end > end_min:
                violations.append(ConstraintViolation(stop_index=i, field="arrival_time", message=f"'{name}' ends after requested end time {req.end_time}", severity="warning"))

        # Time conflict
        if prev_end is not None and arrival_min > 0 and arrival_min < prev_end:
            violations.append(ConstraintViolation(stop_index=i, field="arrival_time", message=f"Time conflict: '{name}' at {arrival} overlaps with previous stop ending at {prev_end//60}:{prev_end%60:02d}", severity="error"))

        # Travel feasibility
        if travel is not None and prev_end is not None and arrival_min > 0:
            gap = arrival_min - prev_end
            if gap < travel - 5:
                violations.append(ConstraintViolation(stop_index=i, field="travel_time_from_prev", message=f"Only {gap} min gap but travel from '{prev_name}' to '{name}' needs {travel} min", severity="error"))

            if prev_lat and prev_lng and lat and lng:
                dist_km = ((lat - prev_lat)**2 + (lng - prev_lng)**2)**0.5 * 111
                min_speed = {"walking": 12, "bicycling": 4, "transit": 2, "driving": 1.5}
                min_realistic = dist_km * min_speed.get(req.travel_mode, 1.5)
                if travel < min_realistic * 0.5:
                    violations.append(ConstraintViolation(stop_index=i, field="travel_time_from_prev", message=f"Travel {travel} min for {dist_km:.1f}km by {req.travel_mode} seems too short", severity="warning"))

        # Budget
        if req.budget and stop.get("price_level"):
            max_level = BUDGET_MAX.get(req.budget, 4)
            if stop["price_level"] > max_level:
                violations.append(ConstraintViolation(stop_index=i, field="price_level", message=f"'{name}' price level {stop['price_level']} exceeds {req.budget} budget", severity="warning"))

        if arrival_min > 0:
            prev_end = arrival_min + duration
        prev_lat, prev_lng, prev_name = lat, lng, name

    return violations


# ============================================================
# TOOLS
# ============================================================

async def search_places(query: str, location: str, radius_meters: int = 10000) -> dict:
    url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
    params = {"query": f"{query} near {location}", "key": GOOGLE_API_KEY, "radius": radius_meters}
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, params=params, timeout=10)
        data = resp.json()
    if data.get("status") not in ("OK", "ZERO_RESULTS"):
        return {"error": data.get("status"), "results": []}
    results = []
    for p in data.get("results", [])[:5]:
        results.append({
            "name": p.get("name"),
            "address": p.get("formatted_address"),
            "place_id": p.get("place_id"),
            "lat": p["geometry"]["location"]["lat"],
            "lng": p["geometry"]["location"]["lng"],
            "rating": p.get("rating"),
            "price_level": p.get("price_level"),
            "open_now": p.get("opening_hours", {}).get("open_now"),
        })
    return {"results": results}


async def get_place_details(place_id: str) -> dict:
    url = "https://maps.googleapis.com/maps/api/place/details/json"
    params = {"place_id": place_id, "fields": "name,formatted_address,opening_hours,formatted_phone_number,website,rating,price_level,geometry", "key": GOOGLE_API_KEY}
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, params=params, timeout=10)
        data = resp.json()
    if data.get("status") != "OK":
        return {"error": data.get("status")}
    r = data["result"]
    hours = r.get("opening_hours", {})
    return {
        "name": r.get("name"), "address": r.get("formatted_address"),
        "phone": r.get("formatted_phone_number"), "website": r.get("website"),
        "rating": r.get("rating"), "price_level": r.get("price_level"),
        "lat": r["geometry"]["location"]["lat"], "lng": r["geometry"]["location"]["lng"],
        "open_now": hours.get("open_now"), "weekday_text": hours.get("weekday_text", []),
    }


async def get_directions(origin_lat: float, origin_lng: float, dest_lat: float, dest_lng: float, departure_time: str, mode: str = "driving") -> dict:
    url = "https://maps.googleapis.com/maps/api/directions/json"
    try:
        dep_unix = int(datetime.fromisoformat(departure_time).timestamp())
    except Exception:
        dep_unix = int(time.time()) + 3600
    params = {"origin": f"{origin_lat},{origin_lng}", "destination": f"{dest_lat},{dest_lng}", "mode": mode, "departure_time": dep_unix, "traffic_model": "best_guess", "key": GOOGLE_API_KEY}
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, params=params, timeout=10)
        data = resp.json()
    if data.get("status") != "OK" or not data.get("routes"):
        return {"error": data.get("status", "NO_ROUTES")}
    leg = data["routes"][0]["legs"][0]
    return {
        "distance_km": round(leg["distance"]["value"] / 1000, 1),
        "duration_minutes": round(leg["duration"]["value"] / 60),
        "duration_in_traffic_minutes": round(leg.get("duration_in_traffic", leg["duration"])["value"] / 60),
        "summary": data["routes"][0].get("summary", ""),
    }


async def get_weather(lat: float, lng: float, date: str) -> dict:
    url = "https://api.open-meteo.com/v1/forecast"
    params = {"latitude": lat, "longitude": lng, "hourly": "temperature_2m,precipitation_probability,weathercode", "temperature_unit": "fahrenheit", "start_date": date, "end_date": date, "timezone": "auto"}
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, params=params, timeout=10)
        data = resp.json()
    hourly = data.get("hourly", {})
    times = hourly.get("time", [])
    temps = hourly.get("temperature_2m", [])
    precip = hourly.get("precipitation_probability", [])
    codes = hourly.get("weathercode", [])
    forecast = []
    for i, t in enumerate(times):
        hour = int(t.split("T")[1].split(":")[0])
        if 6 <= hour <= 22:
            forecast.append({"time": t, "hour": hour, "temp_f": temps[i] if i < len(temps) else None, "precip_pct": precip[i] if i < len(precip) else None, "condition": _weathercode_to_label(codes[i] if i < len(codes) else 0)})
    return {"forecast": forecast, "timezone": data.get("timezone")}


def _weathercode_to_label(code: int) -> str:
    if code == 0: return "Clear"
    if code in (1,2,3): return "Partly cloudy"
    if code in (45,48): return "Foggy"
    if code in (51,53,55): return "Drizzle"
    if code in (61,63,65): return "Rain"
    if code in (71,73,75): return "Snow"
    if code in (80,81,82): return "Rain showers"
    if code in (95,96,99): return "Thunderstorm"
    return "Unknown"


async def get_busyness(place_id: str, venue_name: str, address: str, day_of_week: int) -> dict:
    day_name = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"][day_of_week]
    return {"source": "heuristic", "note": f"Restaurants peak Fri/Sat 6-8pm; parks peak Sat/Sun 11am-3pm; grocery stores peak weekdays 5-7pm. Today is {day_name}."}


def _add_one_day(date_str: str) -> str:
    return (datetime.strptime(date_str, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")


async def _get_dma_id(city: str) -> Optional[str]:
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get("https://app.ticketmaster.com/discovery/v2/markets.json", params={"apikey": TICKETMASTER_API_KEY}, timeout=10)
            data = resp.json()
        for m in data.get("_embedded", {}).get("markets", []):
            if city.lower() in m.get("name", "").lower():
                return str(m.get("id"))
    except Exception:
        pass
    return None


async def _get_utc_bounds(date: str, city: str) -> tuple[str, str]:
    try:
        async with httpx.AsyncClient() as client:
            geo = await client.get("https://maps.googleapis.com/maps/api/geocode/json", params={"address": city, "key": GOOGLE_API_KEY}, timeout=10)
            geo_data = geo.json()
        if geo_data.get("results"):
            loc = geo_data["results"][0]["geometry"]["location"]
            async with httpx.AsyncClient() as client:
                tz = await client.get("https://maps.googleapis.com/maps/api/timezone/json", params={"location": f"{loc['lat']},{loc['lng']}", "timestamp": int(time.time()), "key": GOOGLE_API_KEY}, timeout=10)
                tz_name = tz.json().get("timeZoneId", "America/New_York")
        else:
            tz_name = "America/New_York"
    except Exception:
        tz_name = "America/New_York"
    tz = zoneinfo.ZoneInfo(tz_name)
    local_start = datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=tz)
    local_end = local_start + timedelta(days=1)
    return (local_start.astimezone(zoneinfo.ZoneInfo("UTC")).strftime("%Y-%m-%dT%H:%M:%SZ"),
            local_end.astimezone(zoneinfo.ZoneInfo("UTC")).strftime("%Y-%m-%dT%H:%M:%SZ"))


async def search_events(location: str, date: str, keyword: str = "") -> dict:
    if not TICKETMASTER_API_KEY:
        return {"events": [], "message": "No Ticketmaster key"}
    city = location.split(",")[0].strip()
    start_utc, end_utc = await _get_utc_bounds(date, city)
    dma_id = await _get_dma_id(city)
    params = {"apikey": TICKETMASTER_API_KEY, "startDateTime": start_utc, "endDateTime": end_utc, "size": 50, "sort": "date,asc"}
    if dma_id: params["dmaId"] = dma_id
    else: params["city"] = city
    if keyword: params["keyword"] = keyword
    async with httpx.AsyncClient() as client:
        resp = await client.get("https://app.ticketmaster.com/discovery/v2/events.json", params=params, timeout=10)
        data = resp.json()
    events = data.get("_embedded", {}).get("events", [])
    if not events:
        return {"events": [], "message": "No events found"}
    city_lower = city.lower()
    results = []
    for e in events:
        venue = e.get("_embedded", {}).get("venues", [{}])[0]
        if city_lower not in venue.get("city", {}).get("name", "").lower():
            continue
        results.append({
            "name": e.get("name"), "date": e.get("dates", {}).get("start", {}).get("localDate"),
            "time": e.get("dates", {}).get("start", {}).get("localTime"),
            "venue_name": venue.get("name"), "address": venue.get("address", {}).get("line1"),
            "city": venue.get("city", {}).get("name"),
            "lat": float(venue.get("location", {}).get("latitude", 0) or 0),
            "lng": float(venue.get("location", {}).get("longitude", 0) or 0),
            "genre": e.get("classifications", [{}])[0].get("segment", {}).get("name"),
            "price_min": e.get("priceRanges", [{}])[0].get("min") if e.get("priceRanges") else None,
            "price_max": e.get("priceRanges", [{}])[0].get("max") if e.get("priceRanges") else None,
            "url": e.get("url"),
        })
        if len(results) >= 6: break
    return {"events": results} if results else {"events": [], "message": f"No events in {city}"}


# ============================================================
# TOOL DEFINITIONS
# ============================================================

TOOLS = [
    {"name": "search_places", "description": "Search for places near a location. Use specific venue addresses when searching nearby e.g. 'pizza near 2505 1st Ave Seattle'.", "input_schema": {"type": "object", "properties": {"query": {"type": "string"}, "location": {"type": "string"}, "radius_meters": {"type": "integer", "default": 10000}}, "required": ["query", "location"]}},
    {"name": "get_place_details", "description": "Get opening hours, price level, and coordinates for a place by place_id.", "input_schema": {"type": "object", "properties": {"place_id": {"type": "string"}}, "required": ["place_id"]}},
    {"name": "get_directions", "description": "Get travel time between two coordinates with real-time traffic.", "input_schema": {"type": "object", "properties": {"origin_lat": {"type": "number"}, "origin_lng": {"type": "number"}, "dest_lat": {"type": "number"}, "dest_lng": {"type": "number"}, "departure_time": {"type": "string"}, "mode": {"type": "string", "enum": ["driving", "walking", "transit", "bicycling"], "default": "driving"}}, "required": ["origin_lat", "origin_lng", "dest_lat", "dest_lng", "departure_time"]}},
    {"name": "get_weather", "description": "Get hourly weather forecast.", "input_schema": {"type": "object", "properties": {"lat": {"type": "number"}, "lng": {"type": "number"}, "date": {"type": "string"}}, "required": ["lat", "lng", "date"]}},
    {"name": "get_busyness", "description": "Get crowd estimate for a venue.", "input_schema": {"type": "object", "properties": {"place_id": {"type": "string"}, "venue_name": {"type": "string"}, "address": {"type": "string"}, "day_of_week": {"type": "integer"}}, "required": ["place_id", "venue_name", "address", "day_of_week"]}},
    {"name": "search_events", "description": "Search local events. Call this FIRST before searching for other venues.", "input_schema": {"type": "object", "properties": {"location": {"type": "string"}, "date": {"type": "string"}, "keyword": {"type": "string"}}, "required": ["location", "date"]}},
]

SYSTEM_PROMPT = """You are DayAgent, an expert daily itinerary planner.

## Planning order
1. Events and fixed stops are already provided in the context. Use them to anchor the plan geographically.
2. Search for flexible stops (restaurants, cafes, parks) NEAR fixed stop addresses — not near the city.
3. Get place details for opening hours and price level.
4. Get busyness for restaurants without reservations.
5. Get directions between consecutive stops.
6. Optimize order: minimize travel, avoid crowds, respect hours.

## Rules
- Use venue addresses when searching nearby (e.g. "pizza near 2505 1st Ave Seattle").
- Verify day of week before referencing hours.
- Default start: 10:00 AM unless specified.
- Only add extra stops if user wants a full day.
- Return ONLY valid JSON.

## Output schema
{
  "stops": [{
    "name": "string", "address": "string", "place_id": "string",
    "lat": number, "lng": number, "arrival_time": "HH:MM",
    "duration_minutes": number, "travel_time_from_prev": number or null,
    "notes": "string", "category": "restaurant|park|entertainment|shopping|other",
    "price_level": number or null, "rating": number or null,
    "is_flexible": boolean,
    "options": [{"name": "string", "address": "string", "place_id": "string", "lat": number, "lng": number, "notes": "string", "category": "string", "price_level": number or null, "rating": number or null, "url": "string or null"}] or null,
    "selected_option_index": 0
  }],
  "summary": "string", "reasoning": "string", "warnings": ["string"]
}

For flexible stops: set is_flexible true, include 2-3 options (first = recommendation).
For fixed stops: is_flexible false, options null."""


async def dispatch_tool(tool_name: str, tool_input: dict) -> str:
    try:
        if tool_name == "search_places": result = await search_places(**tool_input)
        elif tool_name == "get_place_details": result = await get_place_details(**tool_input)
        elif tool_name == "get_directions": result = await get_directions(**tool_input)
        elif tool_name == "get_weather": result = await get_weather(**tool_input)
        elif tool_name == "get_busyness": result = await get_busyness(**tool_input)
        elif tool_name == "search_events": result = await search_events(**tool_input)
        else: result = {"error": f"Unknown tool: {tool_name}"}
    except Exception as e:
        result = {"error": str(e)}
    return json.dumps(result)


# ============================================================
# STEP 1: INTERPRET INPUT
# ============================================================

async def interpret_input(message: str, location: str, date: str, travel_mode: str, budget: Optional[str], start_time: Optional[str], end_time: Optional[str]) -> dict:
    day_of_week = datetime.strptime(date, "%Y-%m-%d").strftime("%A")
    prompt = f"""Extract planning constraints from this request.
Date: {date} ({day_of_week}), Location: {location}, Travel: {travel_mode}, Budget: {budget or "unspecified"}
Message: "{message}"

Return ONLY JSON:
{{"fixed_stops": [], "flexible_stops": [], "wants_events": true, "wants_full_day": false, "time_constraints": [], "preferences": []}}"""
    response = anthropic_client.messages.create(model="claude-haiku-4-5", max_tokens=512, messages=[{"role": "user", "content": prompt}])
    try:
        text = response.content[0].text
        return json.loads(re.sub(r"```json|```", "", text).strip())
    except Exception:
        return {"fixed_stops": [], "flexible_stops": [], "wants_events": True, "wants_full_day": False, "time_constraints": [], "preferences": []}


# ============================================================
# STEP 2: PRE-FETCH CONTEXT
# ============================================================

async def prefetch_context(location: str, date: str) -> dict:
    import asyncio
    async with httpx.AsyncClient() as client:
        geo = await client.get("https://maps.googleapis.com/maps/api/geocode/json", params={"address": location, "key": GOOGLE_API_KEY}, timeout=10)
        geo_data = geo.json()
    lat, lng = 47.6062, -122.3321
    if geo_data.get("results"):
        loc = geo_data["results"][0]["geometry"]["location"]
        lat, lng = loc["lat"], loc["lng"]
    weather, events = await asyncio.gather(get_weather(lat, lng, date), search_events(location, date))
    return {"lat": lat, "lng": lng, "weather": weather, "events": events}


# ============================================================
# STEP 3: AGENT LOOP
# ============================================================

async def run_agent_loop(message: str, location: str, date: str, travel_mode: str, context: dict, interpreted: dict) -> dict:
    day_of_week = datetime.strptime(date, "%Y-%m-%d").strftime("%A")
    forecasts = context["weather"].get("forecast", [])
    temps = [f["temp_f"] for f in forecasts if f.get("temp_f")]
    conditions = list(set(f["condition"] for f in forecasts if f.get("condition")))
    weather_summary = f"Weather: {min(temps):.0f}-{max(temps):.0f}°F, {', '.join(conditions[:2])}" if temps else ""

    events = context["events"].get("events", [])
    events_summary = ""
    if events:
        events_summary = "\n\nEvents today:\n" + "\n".join(
            f"- {e['name']} at {e.get('venue_name')} ({e.get('address', '')}) at {e.get('time', 'TBD')} — ${e.get('price_min','?')}-{e.get('price_max','?')}"
            for e in events[:6]
        )

    user_content = f"""Plan my day in {location} on {date} ({day_of_week}).
Travel mode: {travel_mode}
{weather_summary}{events_summary}

What I want: {message}

Constraints: {json.dumps(interpreted)}

Search for restaurants/activities NEAR event venues or fixed stops, not near the city."""

    messages = [{"role": "user", "content": user_content}]

    for _ in range(12):
        response = anthropic_client.messages.create(model="claude-haiku-4-5", max_tokens=4096, system=SYSTEM_PROMPT, tools=TOOLS, messages=messages)
        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "end_turn":
            for block in response.content:
                if hasattr(block, "text"):
                    try:
                        return json.loads(block.text)
                    except json.JSONDecodeError:
                        match = re.search(r'\{[\s\S]+\}', block.text)
                        if match:
                            return json.loads(match.group())
            raise ValueError("No parseable JSON")

        if response.stop_reason != "tool_use":
            break

        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                result_str = await dispatch_tool(block.name, block.input)
                tool_results.append({"type": "tool_result", "tool_use_id": block.id, "content": result_str})
        messages.append({"role": "user", "content": tool_results})

    raise ValueError("Agent did not complete")


# ============================================================
# STEP 4: VALIDATE + REPAIR
# ============================================================

async def validate_and_repair(result: dict, req: PlanRequest, max_repairs: int = 2) -> tuple[dict, list[str]]:
    validation_notes = []

    for attempt in range(max_repairs + 1):
        stops = result.get("stops", [])
        violations = validate_constraints(stops, req)
        errors = [v for v in violations if v.severity == "error"]
        warnings = [v for v in violations if v.severity == "warning"]

        for w in warnings:
            note = f"⚡ {w.message}"
            if note not in validation_notes:
                validation_notes.append(note)

        if not errors:
            break

        if attempt >= max_repairs:
            for e in errors:
                validation_notes.append(f"⚠️ Unfixed: {e.message}")
            break

        error_list = "\n".join(f"- Stop {v.stop_index}: {v.message}" for v in errors)
        repair_prompt = f"""Fix these constraint violations in the itinerary:

{json.dumps(result, indent=2)}

Violations:
{error_list}

Fix only the violations. Return complete corrected JSON only."""

        repair_resp = anthropic_client.messages.create(model="claude-haiku-4-5", max_tokens=4096, messages=[{"role": "user", "content": repair_prompt}])
        try:
            text = repair_resp.content[0].text
            result = json.loads(re.sub(r"```json|```", "", text).strip())
            validation_notes.append(f"✓ Auto-repaired {len(errors)} violation(s)")
        except Exception:
            validation_notes.append(f"⚠️ Repair attempt {attempt+1} failed")
            break

    return result, validation_notes


# ============================================================
# ORCHESTRATOR
# ============================================================

async def run_agent(message: str, location: str, date: str, travel_mode: str = "driving",
                    budget: Optional[str] = None, start_time: Optional[str] = None, end_time: Optional[str] = None) -> tuple[dict, list[str]]:
    interpreted = await interpret_input(message, location, date, travel_mode, budget, start_time, end_time)
    context = await prefetch_context(location, date)
    result = await run_agent_loop(message, location, date, travel_mode, context, interpreted)
    req = PlanRequest(message=message, location=location, date=date, travel_mode=travel_mode, budget=budget, start_time=start_time, end_time=end_time)
    return await validate_and_repair(result, req)


# ============================================================
# ROUTES
# ============================================================

@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/plan", response_model=ItineraryResponse)
async def plan_day(req: PlanRequest):
    try:
        result, validation_notes = await run_agent(req.message, req.location, req.date, req.travel_mode, req.budget, req.start_time, req.end_time)
        result["travel_mode"] = req.travel_mode
        result["validation_notes"] = validation_notes
        return ItineraryResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))