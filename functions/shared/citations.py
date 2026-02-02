"""
Citation extraction and verification system.

Ensures all quotes in generated content exist in source material.
"""

import re
import logging
from dataclasses import dataclass
from typing import Optional
from rapidfuzz import fuzz

logger = logging.getLogger(__name__)


@dataclass
class Citation:
    """A verified citation with source attribution."""
    quote: str
    speaker: str
    title: str
    guest: str
    timestamp: str
    youtube_url: str
    video_id: str
    context: str  # Surrounding text for verification
    similarity_score: float = 1.0

    def to_youtube_link(self) -> str:
        """Generate clickable YouTube timestamp link."""
        seconds = self._timestamp_to_seconds(self.timestamp)
        base_url = self.youtube_url.split("?")[0] if "?" in self.youtube_url else self.youtube_url
        return f"{base_url}?t={seconds}s"

    def _timestamp_to_seconds(self, timestamp: str) -> int:
        """Convert HH:MM:SS to seconds."""
        parts = timestamp.split(":")
        if len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
        elif len(parts) == 2:
            return int(parts[0]) * 60 + int(parts[1])
        return 0

    def format_inline(self) -> str:
        """Format as inline citation."""
        return f'"{self.quote}" — {self.speaker}, "{self.title}" [{self.timestamp}]'

    def format_markdown(self) -> str:
        """Format as markdown with clickable link."""
        link = self.to_youtube_link()
        return f'> "{self.quote}"\n> \n> — {self.speaker}, [{self.title}]({link}) [{self.timestamp}]'

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "quote": self.quote,
            "speaker": self.speaker,
            "title": self.title,
            "guest": self.guest,
            "timestamp": self.timestamp,
            "youtube_url": self.youtube_url,
            "youtube_link": self.to_youtube_link(),
            "similarity_score": self.similarity_score,
        }


class CitationVerifier:
    """
    Verifies quotes against source chunks and extracts citations.

    Usage:
        verifier = CitationVerifier()
        verified = verifier.verify_and_fix(llm_output, source_chunks)
    """

    def __init__(self, similarity_threshold: float = 0.70):
        """Initialize with 70% similarity threshold (lowered from 85% for better LLM paraphrase matching)."""
        self.similarity_threshold = similarity_threshold

    def extract_quotes(self, text: str) -> list[str]:
        """Extract all quoted text from generated content."""
        logger.info(f"Extracting quotes from text of length {len(text)}")
        logger.info(f"Text preview: {text[:300]}...")

        # Match double quotes, handling escaped quotes
        quotes = re.findall(r'"([^"]+)"', text)
        logger.info(f"Found {len(quotes)} regular quotes")

        # Also match smart quotes (Unicode: U+201C and U+201D)
        smart_quotes = re.findall(r'\u201c([^\u201d]+)\u201d', text)
        logger.info(f"Found {len(smart_quotes)} smart quotes")
        quotes.extend(smart_quotes)
        # Deduplicate while preserving order, filter out non-quote content
        seen = set()
        unique_quotes = []
        for q in quotes:
            # Skip if already seen
            if q in seen:
                continue
            # Skip very short strings (likely not actual quotes)
            if len(q) < 15:
                continue
            # Skip strings that look like episode titles (contain | separator)
            if "|" in q:
                continue
            # Skip strings that look like episode titles in citation format
            # Pattern: appears after "— Name," and before "[HH:MM:SS]"
            citation_pattern = rf'— [^,]+,\s*[""]{re.escape(q)}[""].*?\[\d{{2}}:\d{{2}}:\d{{2}}\]'
            if re.search(citation_pattern, text):
                continue
            seen.add(q)
            unique_quotes.append(q)
        return unique_quotes

    def find_quote_in_chunks(
        self,
        quote: str,
        chunks: list[dict],
    ) -> Optional[tuple[dict, float]]:
        """
        Find the source chunk containing a quote using fuzzy matching.

        Args:
            quote: The quote to find
            chunks: List of source chunks

        Returns:
            Tuple of (matching chunk, similarity score) or None
        """
        best_match = None
        best_score = 0

        quote_lower = quote.lower().strip()

        for chunk in chunks:
            content = chunk.get("content", "")
            content_lower = content.lower()

            # Try exact substring match first
            if quote_lower in content_lower:
                return (chunk, 1.0)

            # Fuzzy partial match
            score = fuzz.partial_ratio(quote_lower, content_lower) / 100

            if score > best_score:
                best_score = score
                best_match = chunk

        if best_match and best_score >= self.similarity_threshold:
            return (best_match, best_score)

        return None

    def create_citation(
        self,
        quote: str,
        chunk: dict,
        similarity: float,
    ) -> Citation:
        """Create a Citation object from a chunk."""
        return Citation(
            quote=quote,
            speaker=chunk.get("speaker", "Unknown"),
            title=chunk.get("title", "Unknown"),
            guest=chunk.get("guest", "Unknown"),
            timestamp=chunk.get("timestamp_start", "00:00:00"),
            youtube_url=chunk.get("youtube_url", ""),
            video_id=chunk.get("video_id", ""),
            context=chunk.get("content", "")[:500],
            similarity_score=similarity,
        )

    def verify_and_fix(
        self,
        generated_text: str,
        source_chunks: list[dict],
    ) -> tuple[str, list[Citation], list[str]]:
        """
        Verify all quotes in generated text and fix citations.

        Args:
            generated_text: LLM-generated text with quotes
            source_chunks: Source chunks used for generation

        Returns:
            Tuple of (fixed_text, verified_citations, unverified_quotes)
        """
        quotes = self.extract_quotes(generated_text)
        logger.info(f"Extracted {len(quotes)} quotes from generated text")
        logger.info(f"Source chunks: {len(source_chunks)}")
        if quotes:
            logger.info(f"First quote: {quotes[0][:100]}...")
        if source_chunks:
            logger.info(f"First chunk content: {source_chunks[0].get('content', '')[:100]}...")

        verified_citations = []
        unverified_quotes = []
        fixed_text = generated_text

        for quote in quotes:
            result = self.find_quote_in_chunks(quote, source_chunks)

            if result:
                chunk, similarity = result
                logger.info(f"Quote matched with similarity {similarity:.2f}: {quote[:50]}...")
                citation = self.create_citation(quote, chunk, similarity)
                verified_citations.append(citation)

                # Ensure correct citation format in text
                fixed_text = self._ensure_citation_format(
                    fixed_text, quote, citation
                )
            else:
                logger.warning(f"Quote NOT matched: {quote[:80]}...")
                unverified_quotes.append(quote)
                # Flag unverified quotes
                fixed_text = self._flag_unverified(fixed_text, quote)

        logger.info(f"Verification complete: {len(verified_citations)} verified, {len(unverified_quotes)} unverified")
        return fixed_text, verified_citations, unverified_quotes

    def _ensure_citation_format(
        self,
        text: str,
        quote: str,
        citation: Citation,
    ) -> str:
        """Ensure quote has proper citation format."""
        # Pattern: "quote" followed by optional citation
        pattern = rf'"{re.escape(quote)}"(\s*—[^"\n]*)?'

        # Replacement with proper citation
        replacement = f'"{quote}" — {citation.speaker}, "{citation.title}" [{citation.timestamp}]'

        return re.sub(pattern, replacement, text, count=1)

    def _flag_unverified(self, text: str, quote: str) -> str:
        """Flag unverified quotes with a marker."""
        escaped_quote = re.escape(quote)
        # Try regular quotes first
        pattern = rf'"{escaped_quote}"(?!\s*\[⚠️)'
        if re.search(pattern, text):
            return re.sub(pattern, f'"{quote}" [⚠️ UNVERIFIED]', text, count=1)
        # Try smart quotes
        pattern = rf'"{escaped_quote}"(?!\s*\[⚠️)'
        if re.search(pattern, text):
            return re.sub(pattern, f'"{quote}" [⚠️ UNVERIFIED]', text, count=1)
        return text

    def extract_all_citations(
        self,
        generated_text: str,
        source_chunks: list[dict],
    ) -> list[Citation]:
        """
        Extract all verified citations from text.

        Args:
            generated_text: Text with quotes
            source_chunks: Source chunks

        Returns:
            List of verified Citation objects
        """
        _, citations, _ = self.verify_and_fix(generated_text, source_chunks)
        return citations

    def format_citations_section(
        self,
        citations: list[Citation],
    ) -> str:
        """
        Format a sources/citations section for the end of a document.

        Args:
            citations: List of Citation objects

        Returns:
            Formatted markdown sources section
        """
        if not citations:
            return ""

        # Group by transcript
        by_transcript = {}
        for c in citations:
            key = c.title
            if key not in by_transcript:
                by_transcript[key] = {
                    "title": c.title,
                    "guest": c.guest,
                    "youtube_url": c.youtube_url,
                    "timestamps": [],
                }
            by_transcript[key]["timestamps"].append(c.timestamp)

        # Format
        lines = ["", "---", "", "## Sources", ""]
        for info in by_transcript.values():
            timestamps = ", ".join(sorted(set(info["timestamps"])))
            link = info["youtube_url"]
            lines.append(f"- **{info['guest']}**: [{info['title']}]({link}) (Referenced at: {timestamps})")

        return "\n".join(lines)
