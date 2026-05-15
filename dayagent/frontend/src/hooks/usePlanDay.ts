import { useState } from "react"
import type { Itinerary, PlanRequest } from "../types"

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000"

export function usePlanDay() {
  const [itinerary, setItinerary] = useState<Itinerary | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function planDay(req: PlanRequest) {
    setLoading(true)
    setError(null)
    setItinerary(null)
    try {
      const resp = await fetch(`${API_BASE}/plan`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(req),
      })
      if (!resp.ok) {
        const detail = await resp.json().catch(() => ({}))
        throw new Error(detail.detail || `Server error ${resp.status}`)
      }
      const data: Itinerary = await resp.json()
      setItinerary(data)
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unknown error")
    } finally {
      setLoading(false)
    }
  }

  return { itinerary, loading, error, planDay }
}
