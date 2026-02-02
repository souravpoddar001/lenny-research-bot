"""
Transcript chunking module for hierarchical document processing.

Implements a multi-layer chunking strategy:
- Topic Segments (2000-3000 tokens): Broad context
- Speaker Turns (500-1000 tokens): Primary citation unit
- Sentence Groups (200-400 tokens): Fine-grained retrieval
"""

import re
import hashlib
from dataclasses import dataclass, field
from typing import Optional
import frontmatter
import tiktoken


@dataclass
class SpeakerTurn:
    """Represents a single speaker's contiguous dialogue."""
    speaker: str
    text: str
    timestamp_start: str
    timestamp_end: Optional[str] = None

    def __post_init__(self):
        self.text = self.text.strip()


@dataclass
class Chunk:
    """A chunk of transcript content with full attribution."""
    content: str
    chunk_type: str  # topic_segment, speaker_turn, sentence_group
    transcript_id: str
    guest: str
    title: str
    youtube_url: str
    video_id: str
    publish_date: str
    keywords: list[str]
    speaker: str
    timestamp_start: str
    timestamp_end: Optional[str] = None
    chunk_sequence: int = 0
    chunk_id: str = field(default="")

    def __post_init__(self):
        if not self.chunk_id:
            # Generate deterministic chunk ID
            content_hash = hashlib.md5(
                f"{self.transcript_id}:{self.chunk_sequence}:{self.chunk_type}".encode()
            ).hexdigest()[:12]
            self.chunk_id = f"{self.transcript_id}_{self.chunk_type}_{content_hash}"

    def to_dict(self) -> dict:
        """Convert to dictionary for indexing."""
        return {
            "id": self.chunk_id,
            "chunk_id": self.chunk_id,
            "transcript_id": self.transcript_id,
            "guest": self.guest,
            "title": self.title,
            "youtube_url": self.youtube_url,
            "video_id": self.video_id,
            "publish_date": self.publish_date,
            "keywords": self.keywords,
            "speaker": self.speaker,
            "timestamp_start": self.timestamp_start,
            "timestamp_end": self.timestamp_end or "",
            "content": self.content,
            "chunk_sequence": self.chunk_sequence,
            "chunk_type": self.chunk_type,
        }


class TranscriptChunker:
    """
    Hierarchical chunking that preserves speaker attribution and timestamps.

    Usage:
        chunker = TranscriptChunker()
        chunks = chunker.chunk_transcript(markdown_content, transcript_id)
    """

    # Speaker turn pattern: "Speaker Name (HH:MM:SS):" or "[HH:MM:SS] Speaker:"
    SPEAKER_PATTERN_1 = re.compile(
        r'^([A-Za-z\s\-\']+)\s*\((\d{1,2}:\d{2}:\d{2})\):\s*(.+?)(?=^[A-Za-z\s\-\']+\s*\(\d{1,2}:\d{2}:\d{2}\):|$)',
        re.MULTILINE | re.DOTALL
    )
    SPEAKER_PATTERN_2 = re.compile(
        r'\[(\d{1,2}:\d{2}:\d{2})\]\s*([A-Za-z\s\-\']+):\s*(.+?)(?=\[\d{1,2}:\d{2}:\d{2}\]|$)',
        re.DOTALL
    )

    def __init__(
        self,
        topic_segment_tokens: int = 2500,
        speaker_turn_max_tokens: int = 1000,
        sentence_group_tokens: int = 300,
        overlap_tokens: int = 50,
    ):
        self.topic_segment_tokens = topic_segment_tokens
        self.speaker_turn_max_tokens = speaker_turn_max_tokens
        self.sentence_group_tokens = sentence_group_tokens
        self.overlap_tokens = overlap_tokens
        self.tokenizer = tiktoken.get_encoding("cl100k_base")

    def count_tokens(self, text: str) -> int:
        """Count tokens in text."""
        return len(self.tokenizer.encode(text))

    def chunk_transcript(self, markdown_content: str, transcript_id: str) -> list[Chunk]:
        """
        Process a transcript markdown file into hierarchical chunks.

        Args:
            markdown_content: Full markdown content with YAML frontmatter
            transcript_id: Unique identifier for the transcript

        Returns:
            List of Chunk objects ready for indexing
        """
        # Parse frontmatter
        post = frontmatter.loads(markdown_content)
        metadata = {
            "guest": post.get("guest", "Unknown"),
            "title": post.get("title", "Untitled"),
            "youtube_url": post.get("youtube_url", ""),
            "video_id": post.get("video_id", ""),
            "publish_date": str(post.get("publish_date", "")),
            "keywords": post.get("keywords", []),
        }

        dialogue = post.content

        # Extract speaker turns
        speaker_turns = self._extract_speaker_turns(dialogue)

        if not speaker_turns:
            # Fallback: treat entire content as one chunk
            return [self._create_chunk(
                content=dialogue[:10000],  # Limit size
                chunk_type="topic_segment",
                transcript_id=transcript_id,
                metadata=metadata,
                speaker=metadata["guest"],
                timestamp_start="00:00:00",
                sequence=0,
            )]

        chunks = []
        sequence = 0

        # Create speaker turn chunks
        for i, turn in enumerate(speaker_turns):
            # Determine end timestamp from next turn
            end_timestamp = speaker_turns[i + 1].timestamp_start if i + 1 < len(speaker_turns) else None

            chunk = self._create_chunk(
                content=turn.text,
                chunk_type="speaker_turn",
                transcript_id=transcript_id,
                metadata=metadata,
                speaker=turn.speaker,
                timestamp_start=turn.timestamp_start,
                timestamp_end=end_timestamp,
                sequence=sequence,
            )
            chunks.append(chunk)
            sequence += 1

            # If turn is long, create sentence group sub-chunks
            if self.count_tokens(turn.text) > self.speaker_turn_max_tokens:
                sentence_chunks = self._create_sentence_groups(
                    turn, transcript_id, metadata, sequence
                )
                chunks.extend(sentence_chunks)
                sequence += len(sentence_chunks)

        # Create topic segment chunks by grouping speaker turns
        topic_chunks = self._create_topic_segments(
            speaker_turns, transcript_id, metadata, sequence
        )
        chunks.extend(topic_chunks)

        return chunks

    def _extract_speaker_turns(self, dialogue: str) -> list[SpeakerTurn]:
        """Extract speaker turns from dialogue text."""
        turns = []

        # Try pattern 1: "Speaker Name (HH:MM:SS):"
        matches = self.SPEAKER_PATTERN_1.findall(dialogue)
        if matches:
            for speaker, timestamp, text in matches:
                turns.append(SpeakerTurn(
                    speaker=speaker.strip(),
                    timestamp_start=timestamp,
                    text=text.strip(),
                ))
            return turns

        # Try pattern 2: "[HH:MM:SS] Speaker:"
        matches = self.SPEAKER_PATTERN_2.findall(dialogue)
        if matches:
            for timestamp, speaker, text in matches:
                turns.append(SpeakerTurn(
                    speaker=speaker.strip(),
                    timestamp_start=timestamp,
                    text=text.strip(),
                ))
            return turns

        # Fallback: split by common speaker indicators
        lines = dialogue.split('\n')
        current_speaker = "Unknown"
        current_text = []
        current_timestamp = "00:00:00"

        for line in lines:
            # Check for speaker line (e.g., "Lenny:" or "Guest Name:")
            speaker_match = re.match(r'^([A-Za-z\s\-\']+):\s*(.*)$', line)
            if speaker_match:
                # Save previous turn
                if current_text:
                    turns.append(SpeakerTurn(
                        speaker=current_speaker,
                        timestamp_start=current_timestamp,
                        text=' '.join(current_text),
                    ))
                    current_text = []

                current_speaker = speaker_match.group(1).strip()
                if speaker_match.group(2):
                    current_text.append(speaker_match.group(2))
            elif line.strip():
                current_text.append(line.strip())

        # Don't forget the last turn
        if current_text:
            turns.append(SpeakerTurn(
                speaker=current_speaker,
                timestamp_start=current_timestamp,
                text=' '.join(current_text),
            ))

        return turns

    def _create_chunk(
        self,
        content: str,
        chunk_type: str,
        transcript_id: str,
        metadata: dict,
        speaker: str,
        timestamp_start: str,
        timestamp_end: Optional[str] = None,
        sequence: int = 0,
    ) -> Chunk:
        """Create a Chunk object with full attribution."""
        return Chunk(
            content=content,
            chunk_type=chunk_type,
            transcript_id=transcript_id,
            guest=metadata["guest"],
            title=metadata["title"],
            youtube_url=metadata["youtube_url"],
            video_id=metadata["video_id"],
            publish_date=metadata["publish_date"],
            keywords=metadata["keywords"],
            speaker=speaker,
            timestamp_start=timestamp_start,
            timestamp_end=timestamp_end,
            chunk_sequence=sequence,
        )

    def _create_sentence_groups(
        self,
        turn: SpeakerTurn,
        transcript_id: str,
        metadata: dict,
        start_sequence: int,
    ) -> list[Chunk]:
        """Split a long speaker turn into overlapping sentence groups."""
        sentences = re.split(r'(?<=[.!?])\s+', turn.text)
        chunks = []
        current_group = []
        current_tokens = 0
        sequence = start_sequence

        for sentence in sentences:
            sentence_tokens = self.count_tokens(sentence)

            if current_tokens + sentence_tokens > self.sentence_group_tokens and current_group:
                # Create chunk from current group
                chunk = self._create_chunk(
                    content=' '.join(current_group),
                    chunk_type="sentence_group",
                    transcript_id=transcript_id,
                    metadata=metadata,
                    speaker=turn.speaker,
                    timestamp_start=turn.timestamp_start,
                    sequence=sequence,
                )
                chunks.append(chunk)
                sequence += 1

                # Keep last sentence for overlap
                current_group = [current_group[-1]] if current_group else []
                current_tokens = self.count_tokens(current_group[0]) if current_group else 0

            current_group.append(sentence)
            current_tokens += sentence_tokens

        # Don't forget the last group
        if current_group:
            chunk = self._create_chunk(
                content=' '.join(current_group),
                chunk_type="sentence_group",
                transcript_id=transcript_id,
                metadata=metadata,
                speaker=turn.speaker,
                timestamp_start=turn.timestamp_start,
                sequence=sequence,
            )
            chunks.append(chunk)

        return chunks

    def _create_topic_segments(
        self,
        turns: list[SpeakerTurn],
        transcript_id: str,
        metadata: dict,
        start_sequence: int,
    ) -> list[Chunk]:
        """Group speaker turns into larger topic segments."""
        chunks = []
        current_turns = []
        current_tokens = 0
        sequence = start_sequence

        for turn in turns:
            turn_tokens = self.count_tokens(turn.text)

            if current_tokens + turn_tokens > self.topic_segment_tokens and current_turns:
                # Create topic segment
                combined_text = '\n\n'.join(
                    f"**{t.speaker}:** {t.text}" for t in current_turns
                )
                chunk = self._create_chunk(
                    content=combined_text,
                    chunk_type="topic_segment",
                    transcript_id=transcript_id,
                    metadata=metadata,
                    speaker=current_turns[0].speaker,  # Primary speaker
                    timestamp_start=current_turns[0].timestamp_start,
                    timestamp_end=current_turns[-1].timestamp_start,
                    sequence=sequence,
                )
                chunks.append(chunk)
                sequence += 1

                current_turns = []
                current_tokens = 0

            current_turns.append(turn)
            current_tokens += turn_tokens

        # Don't forget the last segment
        if current_turns:
            combined_text = '\n\n'.join(
                f"**{t.speaker}:** {t.text}" for t in current_turns
            )
            chunk = self._create_chunk(
                content=combined_text,
                chunk_type="topic_segment",
                transcript_id=transcript_id,
                metadata=metadata,
                speaker=current_turns[0].speaker,
                timestamp_start=current_turns[0].timestamp_start,
                timestamp_end=current_turns[-1].timestamp_start,
                sequence=sequence,
            )
            chunks.append(chunk)

        return chunks
