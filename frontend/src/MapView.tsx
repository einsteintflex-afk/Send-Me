import { useEffect, useRef } from "react";
import L from "leaflet";

export type Pin = { lat: number; lng: number; label: string; color: string; glyph: string; pulse?: boolean };

/** OpenStreetMap map (no API key). Swap the tile layer for Google Maps when a key is configured. */
export default function MapView({ pins, height = 260 }: { pins: Pin[]; height?: number }) {
  const el = useRef<HTMLDivElement>(null);
  const map = useRef<L.Map | null>(null);
  const layer = useRef<L.LayerGroup | null>(null);
  useEffect(() => {
    if (!el.current || map.current) return;
    map.current = L.map(el.current, { zoomControl: true, attributionControl: true, zoomAnimation: false, fadeAnimation: false, markerZoomAnimation: false }).setView([5.65, -0.187], 16);
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", { maxZoom: 19, attribution: "© OpenStreetMap contributors" }).addTo(map.current);
    layer.current = L.layerGroup().addTo(map.current);
    return () => { layer.current = null; try { map.current?.stop(); map.current?.remove(); } catch { /* already gone */ } map.current = null; };
  }, []);
  useEffect(() => {
    if (!map.current || !layer.current) return;
    layer.current.clearLayers();
    const pts: L.LatLngExpression[] = [];
    pins.forEach((p) => {
      const icon = L.divIcon({ className: "", iconSize: [30, 30], iconAnchor: [15, 30],
        html: `<div class="pin ${p.pulse ? "pulse" : ""}" style="background:${p.color}"><span>${p.glyph}</span></div>` });
      L.marker([p.lat, p.lng], { icon, title: p.label }).bindTooltip(p.label).addTo(layer.current!);
      pts.push([p.lat, p.lng]);
    });
    if (pts.length > 1) { L.polyline(pts, { color: "#16A6A0", weight: 3, dashArray: "6 8" }).addTo(layer.current); map.current.fitBounds(L.latLngBounds(pts), { padding: [40, 40], maxZoom: 18, animate: false }); }
    else if (pts.length === 1) map.current.setView(pts[0], 17, { animate: false });
    const m = map.current;
    const t = window.setTimeout(() => { try { if (map.current === m) m.invalidateSize(); } catch { /* map was torn down */ } }, 60);
    return () => clearTimeout(t);
  }, [pins]);
  return <div ref={el} style={{ height }} className="w-full overflow-hidden rounded-2xl bg-mint" role="img" aria-label="Map" />;
}
