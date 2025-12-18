import React from 'react';

export default function EpimetheusLogo({ className = "w-10 h-10" }) {
  return (
    <svg
      className={className}
      viewBox="0 0 100 100"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
    >
      <defs>
        {/* Gradient background - purple to teal/greenish-gray */}
        <linearGradient id="epimetheusGradient" x1="0%" y1="0%" x2="100%" y2="0%">
          <stop offset="0%" stopColor="#4A154B" />
          <stop offset="100%" stopColor="#2C5F5F" />
        </linearGradient>
      </defs>
      
      {/* Rounded square container without border */}
      <rect
        x="0"
        y="0"
        width="100"
        height="100"
        rx="10"
        fill="url(#epimetheusGradient)"
      />

      {/* Speech bubble on left with three dots */}
      <g>
        <path
          d="M 18 38 Q 18 28 28 28 L 38 28 Q 48 28 48 38 L 48 48 Q 48 58 38 58 L 33 58 L 28 63 L 28 58 Q 18 58 18 48 Z"
          stroke="white"
          strokeWidth="3"
          fill="none"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        {/* Three horizontal dots - dark gray */}
        <circle cx="28" cy="40" r="1.5" fill="#4A4A4A" />
        <circle cx="33" cy="40" r="1.5" fill="#4A4A4A" />
        <circle cx="38" cy="40" r="1.5" fill="#4A4A4A" />
      </g>

      {/* Central grid (3x3 pattern) */}
      <g>
        {/* Grid circles - 3x3 */}
        <circle cx="50" cy="32" r="3.5" stroke="white" strokeWidth="2.5" fill="none" />
        <circle cx="50" cy="42" r="3.5" stroke="white" strokeWidth="2.5" fill="none" />
        <circle cx="50" cy="52" r="3.5" stroke="white" strokeWidth="2.5" fill="none" />
        <circle cx="62" cy="32" r="3.5" stroke="white" strokeWidth="2.5" fill="none" />
        <circle cx="62" cy="42" r="3.5" stroke="white" strokeWidth="2.5" fill="none" />
        <circle cx="62" cy="52" r="3.5" stroke="white" strokeWidth="2.5" fill="none" />
        <circle cx="74" cy="32" r="3.5" stroke="white" strokeWidth="2.5" fill="none" />
        <circle cx="74" cy="42" r="3.5" stroke="white" strokeWidth="2.5" fill="none" />
        <circle cx="74" cy="52" r="3.5" stroke="white" strokeWidth="2.5" fill="none" />
        
        {/* Horizontal connecting lines */}
        <line x1="50" y1="32" x2="74" y2="32" stroke="white" strokeWidth="2" />
        <line x1="50" y1="42" x2="74" y2="42" stroke="white" strokeWidth="2" />
        <line x1="50" y1="52" x2="74" y2="52" stroke="white" strokeWidth="2" />
        
        {/* Vertical connecting lines */}
        <line x1="50" y1="32" x2="50" y2="52" stroke="white" strokeWidth="2" />
        <line x1="62" y1="32" x2="62" y2="52" stroke="white" strokeWidth="2" />
        <line x1="74" y1="32" x2="74" y2="52" stroke="white" strokeWidth="2" />
        
        {/* X in center circle (62, 42) */}
        <line x1="59" y1="39" x2="65" y2="45" stroke="white" strokeWidth="2.5" strokeLinecap="round" />
        <line x1="65" y1="39" x2="59" y2="45" stroke="white" strokeWidth="2.5" strokeLinecap="round" />
        
        {/* Green square accent at bottom-right circle (74, 52) */}
        <rect
          x="75.5"
          y="53.5"
          width="3"
          height="3"
          fill="#2EB67D"
          rx="0.5"
        />
      </g>

      {/* Two overlapping documents on right */}
      <g>
        {/* Back document with folded corner */}
        <path
          d="M 78 28 L 85 28 L 88 31 L 88 56 L 78 56 Z"
          stroke="white"
          strokeWidth="2.5"
          fill="none"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        <path
          d="M 85 28 L 88 31 L 85 31 Z"
          stroke="white"
          strokeWidth="2.5"
          fill="none"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        {/* Front document with folded corner */}
        <path
          d="M 81 31 L 88 31 L 91 34 L 91 59 L 81 59 Z"
          stroke="white"
          strokeWidth="2.5"
          fill="none"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        <path
          d="M 88 31 L 91 34 L 88 34 Z"
          stroke="white"
          strokeWidth="2.5"
          fill="none"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        {/* Three horizontal lines in front document - dark gray */}
        <line x1="83" y1="38" x2="89" y2="38" stroke="#4A4A4A" strokeWidth="1.5" strokeLinecap="round" />
        <line x1="83" y1="43" x2="89" y2="43" stroke="#4A4A4A" strokeWidth="1.5" strokeLinecap="round" />
        <line x1="83" y1="48" x2="89" y2="48" stroke="#4A4A4A" strokeWidth="1.5" strokeLinecap="round" />
      </g>

      {/* Curved connecting line from speech bubble (bottom-right) to grid (top-left) */}
      <path
        d="M 48 50 Q 45 45 50 32"
        stroke="white"
        strokeWidth="3"
        fill="none"
        strokeLinecap="round"
      />
      {/* Blue dot on the connecting line, closer to speech bubble */}
      <circle cx="46" cy="48" r="2.5" fill="#4285F4" />
      
      {/* Curved connecting line from grid (bottom-right) to documents */}
      <path
        d="M 74 52 Q 78 50 81 40"
        stroke="white"
        strokeWidth="3"
        fill="none"
        strokeLinecap="round"
      />
      {/* Yellow dot on the connecting line, closer to grid */}
      <circle cx="76" cy="51" r="2.5" fill="#ECB22E" />
    </svg>
  );
}

