import React from 'react';

/**
 * ChakraEmblem — Restrained technical emblem inspired by Ashoka Chakra geometry.
 *
 * Designed as a precision maritime coordinate dial with 24 radial spokes/ticks,
 * representing 24-hour vigilance and nautical navigation.
 * Note: An independent technical geometric emblem for research prototypes;
 * does not copy official government seals.
 */
export default function ChakraEmblem({
  size = 28,
  className = '',
  spin = false,
  color = 'currentColor',
  accentColor = '#FF9933',
}) {
  const radius = 10;
  const center = 12;

  // 24 technical radial spokes at 15-degree intervals
  const spokes = Array.from({ length: 24 }).map((_, i) => {
    const angle = (i * 15 * Math.PI) / 180;
    const x1 = center + 3.2 * Math.cos(angle);
    const y1 = center + 3.2 * Math.sin(angle);
    const x2 = center + (radius - 1.2) * Math.cos(angle);
    const y2 = center + (radius - 1.2) * Math.sin(angle);
    return (
      <line
        key={i}
        x1={x1.toFixed(2)}
        y1={y1.toFixed(2)}
        x2={x2.toFixed(2)}
        y2={y2.toFixed(2)}
        stroke={color}
        strokeWidth={i % 6 === 0 ? '0.9' : '0.55'}
        strokeOpacity={i % 6 === 0 ? '0.95' : '0.65'}
      />
    );
  });

  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={`shrink-0 ${spin ? 'animate-spin' : ''} ${className}`}
      aria-hidden="true"
    >
      {/* Outer technical coordinate ring */}
      <circle
        cx={center}
        cy={center}
        r={radius}
        stroke={color}
        strokeWidth="1.2"
        strokeOpacity="0.85"
      />
      {/* Concentric inner calibration ring */}
      <circle
        cx={center}
        cy={center}
        r={radius - 1.4}
        stroke={color}
        strokeWidth="0.4"
        strokeDasharray="0.8 1.2"
        strokeOpacity="0.5"
      />
      {/* 24 radial navigation spokes */}
      <g>{spokes}</g>
      {/* Central hub ring */}
      <circle
        cx={center}
        cy={center}
        r="2.8"
        stroke={color}
        strokeWidth="0.8"
        fill="none"
        strokeOpacity="0.9"
      />
      {/* Center core pip */}
      <circle
        cx={center}
        cy={center}
        r="1.2"
        fill={accentColor}
      />
    </svg>
  );
}
