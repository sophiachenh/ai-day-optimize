import type { Itinerary, Stop } from "../types"

const CATEGORY_EMOJI: Record<Stop["category"], string> = {
  restaurant: "🍽",
  park: "🌳",
  entertainment: "🎵",
  shopping: "🛒",
  other: "📍",
}

const TRAVEL_EMOJI: Record<string, string> = {
  driving: "🚗",
  walking: "🚶",
  transit: "🚌",
  bicycling: "🚴",
}
const TRAVEL_LABEL: Record<string, string> = {
  driving: "drive",
  walking: "walk",
  transit: "transit",
  bicycling: "bike",
}

function formatTime(time: string) {
  const [h, m] = time.split(":").map(Number)
  const ampm = h >= 12 ? "PM" : "AM"
  const hour = h % 12 || 12
  return { hour: `${hour}:${m.toString().padStart(2, "0")}`, ampm }
}

function PriceLevel({ level }: { level?: number | null }) {
  if (!level) return null
  const filled = "$".repeat(level)
  return <span className="stop-price">{filled}</span>
}

interface Props {
  itinerary: Itinerary
  activeIndex: number | null
  onSelectStop: (index: number) => void
}

export function Timeline({ itinerary, activeIndex, onSelectStop }: Props) {
  const travelEmoji = TRAVEL_EMOJI[itinerary.travel_mode] || "🚗"
  const travelLabel = TRAVEL_LABEL[itinerary.travel_mode] || "drive"

  return (
    <div className="timeline">
      <div className="timeline-header">
        <h2>Your Day</h2>
        <p className="summary">{itinerary.summary}</p>
      </div>

      {itinerary.warnings.length > 0 && (
        <div className="warnings">
          {itinerary.warnings.map((w, i) => (
            <div key={i} className="warning-item">⚠️ {w}</div>
          ))}
        </div>
      )}

      <div className="stops">
        {itinerary.stops.map((stop, i) => {
          const { hour, ampm } = formatTime(stop.arrival_time)
          const isActive = activeIndex === i

          return (
            <div key={stop.place_id + i}>
              {stop.travel_time_from_prev != null && (
                <div className="travel-gap">
                  <span className="travel-line" />
                  <span className="travel-label">
                    {travelEmoji} {stop.travel_time_from_prev} min {travelLabel}
                  </span>
                  <span className="travel-line" />
                </div>
              )}

              <div
                className={`stop-card ${isActive ? "active" : ""}`}
                onClick={() => onSelectStop(i)}
              >
                <div className="stop-card-top">
                  <div className={`stop-time-block ${isActive ? "active" : ""}`}>
                    <div className="stop-hour">{hour}</div>
                    <div className="stop-ampm">{ampm}</div>
                  </div>

                  <div className="stop-content">
                    <div className="stop-title-row">
                      <span className="stop-emoji">{CATEGORY_EMOJI[stop.category]}</span>
                      <span className="stop-name">{stop.name}</span>
                    </div>
                    <div className="stop-address">{stop.address}</div>
                    <div className="stop-meta">
                      <span className="stop-duration">{stop.duration_minutes} min</span>
                      <PriceLevel level={(stop as any).price_level} />
                      <span className={`stop-category-badge cat-${stop.category}`}>
                        {stop.category}
                      </span>
                    </div>
                  </div>
                </div>

                <div className="stop-notes-row">
                  <p className="stop-notes">{stop.notes}</p>
                </div>
              </div>
            </div>
          )
        })}
      </div>

      <div className="reasoning-box">
        <h3>Agent reasoning</h3>
        <p>{itinerary.reasoning}</p>
      </div>
    </div>
  )
}
