import { useState } from "react"
import type { PlanRequest } from "../types"

interface Props {
  onSubmit: (req: PlanRequest) => void
  loading: boolean
}

export function PlanForm({ onSubmit, loading }: Props) {
  const today = new Date().toISOString().split("T")[0]
  const [message, setMessage] = useState("")
  const [location, setLocation] = useState("")
  const [date, setDate] = useState(today)
  const [travelMode, setTravelMode] = useState("driving")
  const [detecting, setDetecting] = useState(false)

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!message.trim() || !location.trim()) return
    onSubmit({ message, location, date, travel_mode: travelMode })
  }

  async function detectLocation() {
  setDetecting(true)
  navigator.geolocation.getCurrentPosition(
    async (pos) => {
      const { latitude, longitude } = pos.coords
      console.log("Got coords:", latitude, longitude)
      const resp = await fetch(
        `https://maps.googleapis.com/maps/api/geocode/json?latlng=${latitude},${longitude}&key=${import.meta.env.VITE_GOOGLE_API_KEY}`
      )
      const data = await resp.json()
      console.log("Geocode response:", data)
      const components = data.results[0]?.address_components || []
      const city = components.find((c: any) => c.types.includes("locality"))?.long_name || ""
      const state = components.find((c: any) => c.types.includes("administrative_area_level_1"))?.short_name || ""
      console.log("City:", city, "State:", state)
      if (city && state) setLocation(`${city}, ${state}`)
      setDetecting(false)
    },
    (err) => {
      console.error("Geolocation error:", err)
      alert("Could not detect location. Please enter manually.")
      setDetecting(false)
    }
  )
}

  return (
    <form onSubmit={handleSubmit} className="plan-form">
      <div className="field">
        <label htmlFor="location">📍 City / neighborhood</label>
        <div className="location-row">
          <input
            id="location"
            type="text"
            placeholder="Seattle, WA"
            value={location}
            onChange={e => setLocation(e.target.value)}
            required
          />
          <button
            type="button"
            className="detect-btn"
            onClick={detectLocation}
            disabled={detecting}
          >
            {detecting ? "Detecting..." : "📍 Use my location"}
          </button>
        </div>
      </div>

      <div className="field">
        <label htmlFor="date">📅 Date</label>
        <input
          id="date"
          type="date"
          value={date}
          min={today}
          onChange={e => setDate(e.target.value)}
          required
        />
      </div>

      <div className="field">
        <label htmlFor="travel_mode">🚗 How are you getting around?</label>
        <select
          id="travel_mode"
          value={travelMode}
          onChange={e => setTravelMode(e.target.value)}
        >
          <option value="driving">🚗 Driving</option>
          <option value="walking">🚶 Walking</option>
          <option value="transit">🚌 Public Transit</option>
          <option value="bicycling">🚴 Bicycling</option>
        </select>
      </div>

      <div className="field">
        <label htmlFor="message">🗓 What do you want to do?</label>
        <textarea
          id="message"
          rows={4}
          placeholder={
            "e.g. Go to a park in the morning, get Thai food for lunch (no reservation), " +
            "see a live music show in the evening, stop by a grocery store"
          }
          value={message}
          onChange={e => setMessage(e.target.value)}
          required
        />
      </div>

      <div className="suggestions">
        <span className="suggestions-label">Quick prompts:</span>
        {[
          "Plan my full day — surprise me!",
          "Coffee, errands, and dinner",
          "Outdoor activities and food",
          "Find events happening today",
        ].map(s => (
          <button
            key={s}
            type="button"
            className="suggestion-chip"
            onClick={() => setMessage(s)}
          >
            {s}
          </button>
        ))}
      </div>

      <button type="submit" disabled={loading || !message.trim() || !location.trim()}>
        {loading ? (
          <span className="loading-text">
            <span className="spinner" /> Planning your day…
          </span>
        ) : (
          "Plan my day →"
        )}
      </button>

      {loading && (
        <p className="loading-hint">
          The agent is searching for venues, checking hours, and calculating routes.
          This takes about 15–30 seconds.
        </p>
      )}
    </form>
  )
}