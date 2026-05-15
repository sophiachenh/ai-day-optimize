import { useEffect, useRef } from "react"
import type { Stop } from "../types"

const CATEGORY_COLOR: Record<Stop["category"], string> = {
  restaurant: "#f97316",
  park: "#22c55e",
  entertainment: "#a855f7",
  shopping: "#3b82f6",
  other: "#6b7280",
}

interface Props {
  stops: Stop[]
  activeIndex: number | null
  googleApiKey: string
}

declare global {
  interface Window {
    google: typeof google
    initMap: () => void
  }
}

export function MapView({ stops, activeIndex, googleApiKey }: Props) {
  const mapRef = useRef<HTMLDivElement>(null)
  const mapInstanceRef = useRef<google.maps.Map | null>(null)
  const markersRef = useRef<google.maps.Marker[]>([])
  const polylineRef = useRef<google.maps.Polyline | null>(null)

  function initializeMap() {
    if (!mapRef.current || mapInstanceRef.current) return
    mapInstanceRef.current = new window.google.maps.Map(mapRef.current, {
      zoom: 12,
      center: { lat: 47.6062, lng: -122.3321 },
      mapTypeControl: false,
      streetViewControl: false,
      fullscreenControl: false,
      styles: [
        { featureType: "poi", elementType: "labels", stylers: [{ visibility: "off" }] },
      ],
    })
  }

  // Load Google Maps script once
  useEffect(() => {
    if (window.google) {
      initializeMap()
      return
    }
    if (document.querySelector('script[src*="maps.googleapis.com"]')) {
      const interval = setInterval(() => {
        if (window.google) {
          clearInterval(interval)
          initializeMap()
        }
      }, 100)
      return () => clearInterval(interval)
    }
    window.initMap = initializeMap
    const script = document.createElement("script")
    script.src = `https://maps.googleapis.com/maps/api/js?key=${googleApiKey}&callback=initMap`
    script.async = true
    document.head.appendChild(script)
    return () => { delete window.initMap }
  }, [])

  // Draw markers when stops change
  useEffect(() => {
    if (stops.length === 0) return

    const tryRender = () => {
      if (!mapInstanceRef.current) {
        setTimeout(tryRender, 200)
        return
      }

      markersRef.current.forEach(m => m.setMap(null))
      markersRef.current = []
      polylineRef.current?.setMap(null)

      const bounds = new window.google.maps.LatLngBounds()

      stops.forEach((stop, i) => {
        const pos = { lat: stop.lat, lng: stop.lng }
        bounds.extend(pos)

        const marker = new window.google.maps.Marker({
          position: pos,
          map: mapInstanceRef.current!,
          label: { text: String(i + 1), color: "#fff", fontWeight: "bold", fontSize: "13px" },
          icon: {
            path: window.google.maps.SymbolPath.CIRCLE,
            scale: 18,
            fillColor: CATEGORY_COLOR[stop.category],
            fillOpacity: 1,
            strokeColor: "#fff",
            strokeWeight: 2,
          },
          title: stop.name,
          zIndex: i,
        })

        const infoWindow = new window.google.maps.InfoWindow({
          content: `
            <div style="font-family:sans-serif;max-width:200px">
              <strong>${stop.name}</strong><br/>
              <span style="color:#666;font-size:12px">${stop.arrival_time} · ${stop.duration_minutes} min</span><br/>
              <span style="font-size:12px">${stop.notes}</span>
            </div>
          `,
        })

        marker.addListener("click", () => {
          infoWindow.open(mapInstanceRef.current!, marker)
        })

        markersRef.current.push(marker)
      })

      polylineRef.current = new window.google.maps.Polyline({
        path: stops.map(s => ({ lat: s.lat, lng: s.lng })),
        geodesic: true,
        strokeColor: "#6366f1",
        strokeOpacity: 0.7,
        strokeWeight: 3,
      })
      polylineRef.current.setMap(mapInstanceRef.current)
      mapInstanceRef.current.fitBounds(bounds, { padding: 60 })
    }

    tryRender()
  }, [stops])

  // Pan/bounce on active stop
  useEffect(() => {
    if (activeIndex == null || !markersRef.current[activeIndex]) return
    const marker = markersRef.current[activeIndex]
    mapInstanceRef.current?.panTo(marker.getPosition()!)
    mapInstanceRef.current?.setZoom(15)
    marker.setAnimation(window.google.maps.Animation.BOUNCE)
    setTimeout(() => marker.setAnimation(null), 1400)
  }, [activeIndex])

  return <div ref={mapRef} className="map-view" />
}