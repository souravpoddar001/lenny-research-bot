'use client'

type Citation = {
  quote: string
  speaker: string
  title: string
  guest: string
  timestamp: string
  youtube_url: string
  youtube_link: string
}

type CitationCardProps = {
  citation: Citation
}

export function CitationCard({ citation }: CitationCardProps) {
  return (
    <div className="bg-gray-50 dark:bg-gray-800/50 rounded-lg p-4 border border-gray-200 dark:border-gray-700">
      <blockquote className="text-gray-700 dark:text-gray-300 italic mb-3">
        "{citation.quote}"
      </blockquote>
      <div className="flex items-center justify-between text-sm">
        <div>
          <span className="font-medium text-gray-900 dark:text-white">
            {citation.speaker}
          </span>
          <span className="text-gray-500 dark:text-gray-400">
            {' '}in "{citation.title}"
          </span>
        </div>
        <a
          href={citation.youtube_link}
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary-600 hover:text-primary-800 dark:hover:text-primary-400
                   flex items-center gap-1 transition-colors"
        >
          <PlayIcon />
          <span>{citation.timestamp}</span>
        </a>
      </div>
    </div>
  )
}

function PlayIcon() {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      fill="currentColor"
      className="w-4 h-4"
    >
      <path
        fillRule="evenodd"
        d="M4.5 5.653c0-1.426 1.529-2.33 2.779-1.643l11.54 6.348c1.295.712 1.295 2.573 0 3.285L7.28 19.991c-1.25.687-2.779-.217-2.779-1.643V5.653z"
        clipRule="evenodd"
      />
    </svg>
  )
}
