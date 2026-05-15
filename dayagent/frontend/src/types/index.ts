export interface Stop {
  name: string
  address: string
  place_id: string
  lat: number
  lng: number
  arrival_time: string       // "HH:MM"
  duration_minutes: number
  travel_time_from_prev: number | null
  notes: string
  category: "restaurant" | "park" | "entertainment" | "shopping" | "other"
}

export interface Itinerary {
  stops: Stop[]
  summary: string
  reasoning: string
  warnings: string[]
  travel_mode: string
}

export interface PlanRequest {
  message: string
  location: string
  date: string
  travel_mode: string
}
