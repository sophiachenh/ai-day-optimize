import { useState } from "react"
import { PlanForm } from "./components/PlanForm"
import { Timeline } from "./components/Timeline"
import { MapView } from "./components/MapView"
import { usePlanDay } from "./hooks/usePlanDay"
import "./App.css"

const GOOGLE_API_KEY = import.meta.env.VITE_GOOGLE_API_KEY || ""

export default function App() {
  const { itinerary, loading, error, planDay } = usePlanDay()
  const [activeIndex, setActiveIndex] = useState<number | null>(null)

  return (
    <div className="app">
      <header className="header">
        <div className="header-inner">
          <div className="logo">
            <span className="logo-icon">🗺</span>
            <span className="logo-text">DayAgent</span>
          </div>
          <span className="logo-sub">AI-powered daily itinerary planner</span>
        </div>
      </header>

      <main className="main">
        {!itinerary ? (
          <div className="centered">
            <div className="hero">
              <h1>Plan your perfect day</h1>
              <p>
                Tell the agent what you want to do. It'll search for venues, check
                opening hours, avoid crowds, and build you an optimized route.
              </p>
            </div>
            <PlanForm onSubmit={planDay} loading={loading} />
            {error && (
              <div className="error-box">
                <strong>Something went wrong:</strong> {error}
              </div>
            )}
          </div>
        ) : (
          <div className="split-view">
            <aside className="sidebar">
              <button className="back-btn" onClick={() => window.location.reload()}>
                ← Plan a new day
              </button>
              <Timeline
                itinerary={itinerary}
                activeIndex={activeIndex}
                onSelectStop={setActiveIndex}
              />
            </aside>
            <div className="map-panel">
              <MapView
                stops={itinerary.stops}
                activeIndex={activeIndex}
                googleApiKey={GOOGLE_API_KEY}
              />
            </div>
          </div>
        )}
      </main>
    </div>
  )
}