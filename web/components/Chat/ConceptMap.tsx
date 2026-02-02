'use client'

import { SupportingPoint } from '@/lib/types'

type ConceptMapProps = {
  mainInsight: string
  supportingPoints: SupportingPoint[]
}

export function ConceptMap({ mainInsight, supportingPoints }: ConceptMapProps) {
  const centerX = 200
  const centerY = 120
  const radius = 90

  // Calculate positions for supporting points around the center
  const getPointPosition = (index: number, total: number) => {
    const angle = (index * 2 * Math.PI) / total - Math.PI / 2  // Start from top
    return {
      x: centerX + radius * Math.cos(angle),
      y: centerY + radius * Math.sin(angle),
    }
  }

  return (
    <div className="w-full overflow-x-auto">
      <svg
        viewBox="0 0 400 240"
        className="w-full max-w-[500px] mx-auto h-auto"
        style={{ minHeight: '200px' }}
      >
        {/* Connecting lines */}
        {supportingPoints.map((point, index) => {
          const pos = getPointPosition(index, supportingPoints.length)
          return (
            <line
              key={`line-${point.id}`}
              x1={centerX}
              y1={centerY}
              x2={pos.x}
              y2={pos.y}
              stroke={point.color}
              strokeWidth="2"
              strokeOpacity="0.4"
            />
          )
        })}

        {/* Center node - Main Insight */}
        <circle
          cx={centerX}
          cy={centerY}
          r="50"
          fill="var(--color-surface)"
          stroke="var(--color-amber)"
          strokeWidth="3"
        />
        <foreignObject x={centerX - 45} y={centerY - 40} width="90" height="80">
          <div className="flex items-center justify-center h-full p-1">
            <p className="text-[10px] text-center text-[var(--color-text-primary)] font-medium leading-tight">
              {mainInsight.length > 60 ? mainInsight.slice(0, 60) + '...' : mainInsight}
            </p>
          </div>
        </foreignObject>

        {/* Supporting point nodes */}
        {supportingPoints.map((point, index) => {
          const pos = getPointPosition(index, supportingPoints.length)
          return (
            <g key={point.id}>
              <circle
                cx={pos.x}
                cy={pos.y}
                r="35"
                fill="var(--color-surface)"
                stroke={point.color}
                strokeWidth="2"
              />
              <foreignObject x={pos.x - 32} y={pos.y - 28} width="64" height="56">
                <div className="flex items-center justify-center h-full p-1">
                  <p className="text-[9px] text-center text-[var(--color-text-secondary)] leading-tight">
                    {point.label}
                  </p>
                </div>
              </foreignObject>
            </g>
          )
        })}
      </svg>
    </div>
  )
}
