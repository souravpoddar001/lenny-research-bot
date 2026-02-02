'use client'

type CitationMarkerProps = {
  number: number
  citationId: string
  onClick: (citationId: string) => void
}

export function CitationMarker({ number, citationId, onClick }: CitationMarkerProps) {
  return (
    <button
      onClick={() => onClick(citationId)}
      className="citation-marker"
      aria-label={`View citation ${number}`}
    >
      {number}
    </button>
  )
}
