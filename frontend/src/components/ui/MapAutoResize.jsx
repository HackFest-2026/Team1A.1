import { useEffect } from 'react';
import { useMap } from 'react-leaflet';

// Leaflet measures its container only on load; when the layout changes size (window
// resize, responsive reflow, collapsing panels) the map must be told to re-measure,
// otherwise part of it stays blank.
export default function MapAutoResize() {
  const map = useMap();
  useEffect(() => {
    const el = map.getContainer();
    if (typeof ResizeObserver === 'undefined' || !el) return undefined;
    let frame = null;
    const ro = new ResizeObserver(() => {
      if (frame) cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => map.invalidateSize({ pan: false }));
    });
    ro.observe(el);
    return () => {
      ro.disconnect();
      if (frame) cancelAnimationFrame(frame);
    };
  }, [map]);
  return null;
}
