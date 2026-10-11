import React from 'react';

// Minimal stroke icon set (24×24 grid, currentColor). Drawn for this project so the
// interface needs no icon dependency. Decorative by default (aria-hidden); pass `title`
// when the icon carries meaning on its own.
const PATHS = {
  shield: <><path d="M12 3l7 3v5c0 4.5-3 8.3-7 10-4-1.7-7-5.5-7-10V6l7-3z" /><path d="M9 12l2 2 4-4" /></>,
  grid: <><rect x="3.5" y="3.5" width="7" height="7" rx="1.5" /><rect x="13.5" y="3.5" width="7" height="7" rx="1.5" /><rect x="3.5" y="13.5" width="7" height="7" rx="1.5" /><rect x="13.5" y="13.5" width="7" height="7" rx="1.5" /></>,
  alert: <><path d="M12 4l9 16H3l9-16z" /><path d="M12 10v4" /><path d="M12 17.5v.01" /></>,
  radio: <><circle cx="12" cy="12" r="2" /><path d="M7.8 7.8a6 6 0 000 8.4M16.2 7.8a6 6 0 010 8.4M5 5a10 10 0 000 14M19 5a10 10 0 010 14" /></>,
  cloud: <><path d="M7 17h10a4 4 0 00.6-7.96A6 6 0 006.2 9.6 3.75 3.75 0 007 17z" /><path d="M9 20l1-2M13 20l1-2" /></>,
  video: <><rect x="3" y="5" width="13" height="14" rx="2" /><path d="M16 10l5-3v10l-5-3" /></>,
  satellite: <><path d="M5.5 13.5l5 5" /><path d="M8 11l5 5-2 2-5-5z" /><path d="M13 6l5 5-2 2-5-5z" /><path d="M16 4l4 4" /><path d="M4 20c0-2 1-3 2.5-3.5" /></>,
  globe: <><circle cx="12" cy="12" r="8.5" /><path d="M3.5 12h17" /><path d="M12 3.5c2.5 2.6 3.5 5.4 3.5 8.5s-1 5.9-3.5 8.5c-2.5-2.6-3.5-5.4-3.5-8.5s1-5.9 3.5-8.5z" /></>,
  route: <><circle cx="6" cy="18" r="2" /><circle cx="18" cy="6" r="2" /><path d="M8 18h7a3 3 0 000-6H9a3 3 0 010-6h7" /></>,
  pin: <><path d="M12 21s-6-5.3-6-11a6 6 0 0112 0c0 5.7-6 11-6 11z" /><circle cx="12" cy="10" r="2.2" /></>,
  check: <path d="M5 12.5l4.5 4.5L19 7.5" />,
  x: <path d="M6 6l12 12M18 6L6 18" />,
  clock: <><circle cx="12" cy="12" r="8.5" /><path d="M12 7.5V12l3 2" /></>,
  sun: <><circle cx="12" cy="12" r="3.5" /><path d="M12 3v2M12 19v2M3 12h2M19 12h2M5.6 5.6l1.4 1.4M17 17l1.4 1.4M5.6 18.4L7 17M17 7l1.4-1.4" /></>,
  moon: <path d="M19 14.5A7.5 7.5 0 019.5 5a7.5 7.5 0 109.5 9.5z" />,
  monitor: <><rect x="3.5" y="4.5" width="17" height="11" rx="1.5" /><path d="M9 19.5h6M12 15.5v4" /></>,
  layers: <><path d="M12 4l8.5 4.5L12 13 3.5 8.5 12 4z" /><path d="M3.5 12.5L12 17l8.5-4.5" /><path d="M3.5 16.5L12 21l8.5-4.5" /></>,
  chevronDown: <path d="M6 9l6 6 6-6" />,
  chevronUp: <path d="M6 15l6-6 6 6" />,
  database: <><ellipse cx="12" cy="6" rx="7" ry="2.5" /><path d="M5 6v12c0 1.4 3.1 2.5 7 2.5s7-1.1 7-2.5V6" /><path d="M5 12c0 1.4 3.1 2.5 7 2.5s7-1.1 7-2.5" /></>,
  flask: <><path d="M9.5 3.5h5" /><path d="M10 3.5v5.5L5 18a2 2 0 001.8 3h10.4a2 2 0 001.8-3l-5-9V3.5" /><path d="M7.5 14.5h9" /></>,
  info: <><circle cx="12" cy="12" r="8.5" /><path d="M12 11v5" /><path d="M12 8v.01" /></>,
  refresh: <><path d="M19.5 12a7.5 7.5 0 01-13.3 4.8" /><path d="M4.5 12a7.5 7.5 0 0113.3-4.8" /><path d="M18 3.5v4h-4M6 20.5v-4h4" /></>,
  activity: <path d="M3.5 12h4l2.5-6 4 12 2.5-6h4" />,
  users: <><circle cx="9" cy="8.5" r="3" /><path d="M3.5 19c.7-3 2.9-4.5 5.5-4.5s4.8 1.5 5.5 4.5" /><circle cx="17" cy="9.5" r="2.3" /><path d="M16 14.6c2.2-.2 4 1 4.5 3.9" /></>,
  eye: <><path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12z" /><circle cx="12" cy="12" r="2.8" /></>,
  file: <><path d="M14 3.5H7a1.5 1.5 0 00-1.5 1.5v14A1.5 1.5 0 007 20.5h10a1.5 1.5 0 001.5-1.5V8L14 3.5z" /><path d="M14 3.5V8h4.5" /><path d="M9 13h6M9 16.5h4" /></>,
  link: <><path d="M10 14a4 4 0 005.7 0l3-3a4 4 0 00-5.7-5.7l-1 1" /><path d="M14 10a4 4 0 00-5.7 0l-3 3a4 4 0 005.7 5.7l1-1" /></>,
  user: <><circle cx="12" cy="8.5" r="3.5" /><path d="M5 20c.9-3.6 3.6-5.5 7-5.5s6.1 1.9 7 5.5" /></>,
  signal: <><path d="M5 19v-3M10 19v-6M15 19v-9M20 19V7" /></>,
  wifiOff: <><path d="M4 4l16 16" /><path d="M8.5 16.5a5 5 0 017 0M5 12.5a10 10 0 016-2.8M19 12.5a10 10 0 00-2.4-1.6" /><path d="M12 20v.01" /></>,
  navigation: <><polygon points="3 11 22 2 13 21 11 13 3 11" /></>,
  radar: <><circle cx="12" cy="12" r="9" /><circle cx="12" cy="12" r="5" /><circle cx="12" cy="12" r="1.5" /><line x1="12" y1="12" x2="19" y2="5" /></>,
  anchor: <><circle cx="12" cy="5" r="2" /><line x1="12" y1="7" x2="12" y2="21" /><line x1="5" y1="11" x2="19" y2="11" /><path d="M5 15a7 7 0 0014 0" /></>,
  compass: <><circle cx="12" cy="12" r="9" /><polygon points="16.24 7.76 14.12 14.12 7.76 16.24 9.88 9.88 16.24 7.76" fill="currentColor" fillOpacity="0.2" /></>,
};

export default function Icon({ name, size = 16, className = '', title, strokeWidth = 1.75 }) {
  const body = PATHS[name];
  if (!body) return null;
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round"
      className={`shrink-0 ${className}`} aria-hidden={title ? undefined : true} role={title ? 'img' : undefined}>
      {title && <title>{title}</title>}
      {body}
    </svg>
  );
}
