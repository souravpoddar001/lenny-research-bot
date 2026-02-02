#!/usr/bin/env python3
"""
PageIndex generation script for Lenny's Podcast transcripts.

Multi-pass extraction using LLM to build hierarchical index:
1. Episode-level extraction (summary, themes, frameworks)
2. Topic segmentation within episodes (5-15 topics per episode)
3. Quote extraction within topics (2-5 per topic)
4. Cross-episode theme aggregation

Usage:
    # Full build
    python build_pageindex.py --transcripts-dir /path/to/episodes --output-dir ./index

    # Dry run with cost estimate
    python build_pageindex.py --transcripts-dir /path/to/episodes --dry-run

    # Incremental (new episodes only)
    python build_pageindex.py --transcripts-dir /path/to/episodes --output-dir ./index --incremental

    # Single episode
    python build_pageindex.py --file /path/to/transcript.md --output-dir ./index
"""

import os
import sys
import argparse
import json
import re
import yaml
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field, asdict
from typing import Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "functions"))

from openai import AzureOpenAI


# ============================================================================
# Data Models
# ============================================================================

@dataclass
class Quote:
    """A key quote from a topic segment."""
    quote_id: str
    text: str
    speaker: str
    timestamp: str
    youtube_link: str
    context: str
    insight_type: str  # framework, advice, story, data, contrarian


@dataclass
class Topic:
    """A topic segment within an episode."""
    topic_id: str
    title: str
    summary: str
    timestamp_start: str
    timestamp_end: str
    speakers: list[str]
    themes: list[str]
    quotes: list[Quote] = field(default_factory=list)


@dataclass
class Episode:
    """An episode in the index."""
    id: str
    guest: str
    title: str
    publish_date: str
    youtube_url: str
    video_id: str
    duration: str
    summary: str
    key_themes: list[str]
    notable_frameworks: list[str]
    guest_expertise: list[str]
    topics: list[Topic] = field(default_factory=list)


@dataclass
class Theme:
    """A cross-episode theme."""
    id: str
    name: str
    description: str
    episode_ids: list[str]
    subtopics: list[str]
    key_episodes: list[str]
    common_frameworks: list[str]


# ============================================================================
# Prompts
# ============================================================================

PASS1_EPISODE_PROMPT = """You are analyzing a podcast transcript from Lenny's Podcast.

TRANSCRIPT METADATA:
Guest: {guest}
Title: {title}
Date: {publish_date}
Duration: {duration}

TRANSCRIPT (first 10000 characters):
{transcript_excerpt}

Extract the following in JSON format:
{{
  "summary": "2-3 sentence summary of the episode's main insights and what listeners will learn",
  "key_themes": ["list", "of", "5-10", "canonical", "themes"],
  "notable_frameworks": ["Named frameworks, mental models, or methodologies discussed"],
  "guest_expertise": ["Areas where guest demonstrates deep experience or unique insights"]
}}

IMPORTANT: Use these canonical theme names when applicable (pick from this list):
- product-market-fit
- growth-strategy
- product-management
- leadership
- hiring
- company-culture
- onboarding
- retention
- pricing
- fundraising
- founder-journey
- decision-making
- metrics
- experimentation
- go-to-market
- user-research
- design
- engineering-management
- career-growth
- communication
- strategy
- ai-ml
- marketplaces
- b2b-saas
- consumer-products

Only include themes that are substantially discussed (not just mentioned in passing)."""


PASS2_TOPIC_PROMPT = """You are segmenting a podcast transcript into distinct topic segments.

TRANSCRIPT METADATA:
Guest: {guest}
Title: {title}

TRANSCRIPT:
{transcript}

Identify 5-15 distinct topic segments. A topic segment is a coherent discussion about one subject, typically lasting 5-15 minutes.

For each segment provide JSON:
{{
  "topics": [
    {{
      "title": "Descriptive title for this discussion segment (5-10 words)",
      "summary": "1-2 sentence summary of what's discussed and key insights",
      "timestamp_start": "HH:MM:SS (timestamp of first speaker turn in segment)",
      "timestamp_end": "HH:MM:SS (timestamp of last speaker turn in segment)",
      "speakers": ["who speaks in this segment"],
      "themes": ["1-3 relevant canonical themes from the list"]
    }}
  ]
}}

Guidelines:
- Mark transitions when the conversation shifts to a new subject
- Include sponsor reads/ads as a single "Sponsor Break" topic if present
- Intro sections should be titled "Introduction and Background"
- Ensure timestamps are accurate based on the speaker turns provided
- themes should use the canonical theme names listed in the episode extraction"""


PASS3_QUOTE_PROMPT = """Extract the most insightful quotes from this topic segment.

EPISODE: {title}
GUEST: {guest}
TOPIC: {topic_title}
TOPIC SUMMARY: {topic_summary}

SEGMENT TEXT:
{segment_text}

Extract 2-5 quotes that meet these criteria:
- Actionable insights or advice practitioners can apply
- Novel frameworks, mental models, or methodologies
- Memorable, quotable statements
- Counterintuitive observations that challenge conventional wisdom
- Data points or specific examples

For each quote provide JSON:
{{
  "quotes": [
    {{
      "text": "Exact quote text - copy VERBATIM from the segment",
      "speaker": "Speaker name",
      "timestamp": "HH:MM:SS",
      "context": "Brief 1-sentence context for why this quote matters",
      "insight_type": "framework|advice|story|data|contrarian"
    }}
  ]
}}

CRITICAL: Quotes must be EXACT verbatim copies from the segment text. Do not paraphrase or modify.
Only include the most valuable 2-5 quotes, not every interesting statement."""


PASS4_THEME_PROMPT = """Generate a comprehensive overview for this theme based on the episodes that discuss it.

THEME: {theme_name}

EPISODES DISCUSSING THIS THEME:
{episode_summaries}

Create a theme overview in JSON format:
{{
  "description": "2-3 sentence description of what this theme covers across the podcast - what questions it addresses and why it matters",
  "subtopics": ["4-6 key subtopics or questions frequently discussed within this theme"],
  "key_episodes": ["Top 5 episode IDs that provide the best coverage of this theme"],
  "common_frameworks": ["Frameworks, models, or methodologies repeatedly mentioned across episodes"]
}}

Focus on synthesis - what patterns emerge across multiple guests discussing this topic?"""


# ============================================================================
# PageIndex Builder
# ============================================================================

class PageIndexBuilder:
    """Builds the 4-level PageIndex from podcast transcripts."""

    # Canonical themes for normalization
    CANONICAL_THEMES = {
        "product-market-fit", "growth-strategy", "product-management", "leadership",
        "hiring", "company-culture", "onboarding", "retention", "pricing", "fundraising",
        "founder-journey", "decision-making", "metrics", "experimentation", "go-to-market",
        "user-research", "design", "engineering-management", "career-growth", "communication",
        "strategy", "ai-ml", "marketplaces", "b2b-saas", "consumer-products",
    }

    def __init__(
        self,
        output_dir: Path,
        openai_api_key: Optional[str] = None,
        openai_endpoint: Optional[str] = None,
        extraction_model: str = None,  # Defaults to AZURE_OPENAI_DEPLOYMENT or "gpt-5.2"
        aggregation_model: str = None,  # Defaults to AZURE_OPENAI_DEPLOYMENT or "gpt-5.2"
        max_workers: int = 5,
    ):
        self.output_dir = output_dir
        default_model = os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-5.2")
        self.extraction_model = extraction_model or default_model
        self.aggregation_model = aggregation_model or default_model
        self.max_workers = max_workers

        # Store credentials for lazy initialization
        self._openai_api_key = openai_api_key
        self._openai_endpoint = openai_endpoint
        self._openai = None

        # Track token usage for cost estimation
        self.token_usage = {
            "input_tokens": 0,
            "output_tokens": 0,
        }

    @property
    def openai(self):
        """Lazy initialization of OpenAI client."""
        if self._openai is None:
            self._openai = AzureOpenAI(
                api_key=self._openai_api_key or os.environ.get("AZURE_OPENAI_API_KEY"),
                azure_endpoint=self._openai_endpoint or os.environ.get("AZURE_OPENAI_ENDPOINT"),
                api_version=os.environ.get("AZURE_OPENAI_API_VERSION", "2024-12-01-preview"),
            )
        return self._openai

    def build_full_index(
        self,
        transcripts: list[Path],
        dry_run: bool = False,
        incremental: bool = False,
    ) -> dict:
        """
        Build the complete PageIndex from transcripts.

        Args:
            transcripts: List of transcript file paths
            dry_run: If True, estimate costs without making API calls
            incremental: If True, skip episodes already in index

        Returns:
            Complete index dictionary
        """
        print(f"\n{'='*60}")
        print("PAGEINDEX GENERATION")
        print(f"{'='*60}")
        print(f"Transcripts to process: {len(transcripts)}")
        print(f"Dry run: {dry_run}")
        print(f"Incremental: {incremental}")
        print(f"Output directory: {self.output_dir}")
        print()

        # Load existing index if incremental
        existing_episodes = set()
        if incremental and (self.output_dir / "episode_index.json").exists():
            with open(self.output_dir / "episode_index.json") as f:
                existing = json.load(f)
                existing_episodes = set(existing.get("episodes", {}).keys())
            print(f"Found {len(existing_episodes)} existing episodes in index")

        # Filter out already-indexed episodes
        if incremental:
            transcripts = [
                t for t in transcripts
                if self._get_episode_id(t) not in existing_episodes
            ]
            print(f"New episodes to process: {len(transcripts)}")

        if dry_run:
            return self._estimate_costs(transcripts)

        # Pass 1: Episode-level extraction
        print("\n[PASS 1/4] Extracting episode metadata...")
        episodes = self._extract_all_episodes(transcripts)

        # Pass 2: Topic segmentation
        print("\n[PASS 2/4] Segmenting topics...")
        episodes = self._segment_all_topics(episodes, transcripts)

        # Pass 3: Quote extraction
        print("\n[PASS 3/4] Extracting quotes...")
        episodes = self._extract_all_quotes(episodes, transcripts)

        # Pass 4: Theme aggregation
        print("\n[PASS 4/4] Aggregating themes...")
        themes = self._aggregate_themes(episodes)

        # Build and save index
        print("\n[SAVING] Writing index files...")
        index = self._build_index(episodes, themes)
        self._save_index(index)

        # Print summary
        self._print_summary(index)

        return index

    def _get_episode_id(self, transcript_path: Path) -> str:
        """Extract episode ID from transcript path."""
        return transcript_path.parent.name

    def _parse_transcript(self, transcript_path: Path) -> dict:
        """Parse transcript file and extract metadata and content."""
        content = transcript_path.read_text(encoding="utf-8")

        # Parse YAML frontmatter
        frontmatter_match = re.match(r'^---\n(.*?)\n---\n', content, re.DOTALL)
        if frontmatter_match:
            metadata = yaml.safe_load(frontmatter_match.group(1))
            transcript_text = content[frontmatter_match.end():]
        else:
            metadata = {}
            transcript_text = content

        return {
            "metadata": metadata,
            "content": transcript_text,
            "episode_id": self._get_episode_id(transcript_path),
        }

    def _call_llm(self, prompt: str, model: str, json_mode: bool = True) -> dict:
        """Make LLM API call and track tokens."""
        response = self.openai.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"} if json_mode else None,
            temperature=0.3,
            max_completion_tokens=4000,
        )

        # Track usage
        if response.usage:
            self.token_usage["input_tokens"] += response.usage.prompt_tokens
            self.token_usage["output_tokens"] += response.usage.completion_tokens

        content = response.choices[0].message.content
        if json_mode:
            return json.loads(content)
        return {"content": content}

    def _extract_all_episodes(self, transcripts: list[Path]) -> list[Episode]:
        """Pass 1: Extract episode-level metadata from all transcripts."""
        episodes = []

        for i, path in enumerate(transcripts, 1):
            print(f"  [{i}/{len(transcripts)}] {self._get_episode_id(path)}...", end=" ")

            try:
                parsed = self._parse_transcript(path)
                meta = parsed["metadata"]
                content = parsed["content"]

                # Prepare prompt
                prompt = PASS1_EPISODE_PROMPT.format(
                    guest=meta.get("guest", "Unknown"),
                    title=meta.get("title", "Unknown"),
                    publish_date=meta.get("publish_date", "Unknown"),
                    duration=meta.get("duration", "Unknown"),
                    transcript_excerpt=content[:10000],
                )

                # Call LLM
                result = self._call_llm(prompt, self.extraction_model)

                # Normalize themes
                key_themes = [
                    t.lower().replace(" ", "-")
                    for t in result.get("key_themes", [])
                ]
                key_themes = [t for t in key_themes if t in self.CANONICAL_THEMES]

                # Validate metadata
                guest = meta.get("guest", "Unknown")
                title = meta.get("title", "")
                if not title or title == "Unknown":
                    title = f"{guest} | Lenny's Podcast"
                    print(f"  [WARNING] Missing title, using: {title}")

                episode = Episode(
                    id=parsed["episode_id"],
                    guest=guest,
                    title=title,
                    publish_date=str(meta.get("publish_date", "")),
                    youtube_url=meta.get("youtube_url", ""),
                    video_id=meta.get("video_id", ""),
                    duration=meta.get("duration", ""),
                    summary=result.get("summary", ""),
                    key_themes=key_themes,
                    notable_frameworks=result.get("notable_frameworks", []),
                    guest_expertise=result.get("guest_expertise", []),
                )
                episodes.append(episode)
                print(f"OK ({len(key_themes)} themes)")

            except Exception as e:
                print(f"ERROR: {e}")

        return episodes

    def _segment_all_topics(
        self,
        episodes: list[Episode],
        transcripts: list[Path],
    ) -> list[Episode]:
        """Pass 2: Segment each episode into topics."""
        transcript_map = {self._get_episode_id(p): p for p in transcripts}

        for i, episode in enumerate(episodes, 1):
            print(f"  [{i}/{len(episodes)}] {episode.id}...", end=" ")

            try:
                path = transcript_map.get(episode.id)
                if not path:
                    print("SKIP (no transcript)")
                    continue

                parsed = self._parse_transcript(path)
                content = parsed["content"]

                prompt = PASS2_TOPIC_PROMPT.format(
                    guest=episode.guest,
                    title=episode.title,
                    transcript=content[:50000],  # Limit for context window
                )

                result = self._call_llm(prompt, self.extraction_model)
                topics_data = result.get("topics", [])

                topics = []
                for j, t in enumerate(topics_data):
                    topic = Topic(
                        topic_id=f"{episode.id}_t{j+1}",
                        title=t.get("title", ""),
                        summary=t.get("summary", ""),
                        timestamp_start=t.get("timestamp_start", "00:00:00"),
                        timestamp_end=t.get("timestamp_end", "00:00:00"),
                        speakers=t.get("speakers", []),
                        themes=t.get("themes", []),
                    )
                    topics.append(topic)

                episode.topics = topics
                print(f"OK ({len(topics)} topics)")

            except Exception as e:
                print(f"ERROR: {e}")

        return episodes

    def _extract_all_quotes(
        self,
        episodes: list[Episode],
        transcripts: list[Path],
    ) -> list[Episode]:
        """Pass 3: Extract key quotes from each topic."""
        transcript_map = {self._get_episode_id(p): p for p in transcripts}

        total_topics = sum(len(e.topics) for e in episodes)
        processed = 0

        for episode in episodes:
            path = transcript_map.get(episode.id)
            if not path:
                continue

            parsed = self._parse_transcript(path)
            content = parsed["content"]

            for topic in episode.topics:
                processed += 1
                print(f"  [{processed}/{total_topics}] {episode.id}/{topic.topic_id}...", end=" ")

                try:
                    # Extract segment text based on timestamps
                    segment_text = self._extract_segment(
                        content,
                        topic.timestamp_start,
                        topic.timestamp_end,
                    )

                    if len(segment_text) < 100:
                        print("SKIP (segment too short)")
                        continue

                    prompt = PASS3_QUOTE_PROMPT.format(
                        title=episode.title,
                        guest=episode.guest,
                        topic_title=topic.title,
                        topic_summary=topic.summary,
                        segment_text=segment_text[:8000],
                    )

                    result = self._call_llm(prompt, self.extraction_model)
                    quotes_data = result.get("quotes", [])

                    quotes = []
                    for k, q in enumerate(quotes_data):
                        # Build YouTube link with timestamp
                        timestamp = q.get("timestamp", topic.timestamp_start)
                        seconds = self._timestamp_to_seconds(timestamp)
                        # Only create youtube_link if we have a valid URL
                        if episode.youtube_url and episode.youtube_url.startswith("http"):
                            youtube_link = f"{episode.youtube_url}&t={seconds}s"
                        else:
                            youtube_link = ""  # Empty instead of broken fragment

                        quote = Quote(
                            quote_id=f"{topic.topic_id}_q{k+1}",
                            text=q.get("text", ""),
                            speaker=q.get("speaker", ""),
                            timestamp=timestamp,
                            youtube_link=youtube_link,
                            context=q.get("context", ""),
                            insight_type=q.get("insight_type", "advice"),
                        )
                        quotes.append(quote)

                    topic.quotes = quotes
                    print(f"OK ({len(quotes)} quotes)")

                except Exception as e:
                    print(f"ERROR: {e}")

        return episodes

    def _extract_segment(
        self,
        content: str,
        start_ts: str,
        end_ts: str,
    ) -> str:
        """Extract transcript text between two timestamps."""
        lines = content.split("\n")
        segment_lines = []
        in_segment = False

        start_seconds = self._timestamp_to_seconds(start_ts)
        end_seconds = self._timestamp_to_seconds(end_ts)

        # Patterns for timestamps
        pattern1 = re.compile(r'\((\d{2}:\d{2}:\d{2})\)')  # (HH:MM:SS)
        pattern2 = re.compile(r'\[(\d{2}:\d{2}:\d{2})\]')  # [HH:MM:SS]

        for line in lines:
            # Check for timestamp
            match = pattern1.search(line) or pattern2.search(line)
            if match:
                ts = match.group(1)
                line_seconds = self._timestamp_to_seconds(ts)

                if line_seconds >= start_seconds and not in_segment:
                    in_segment = True
                elif line_seconds > end_seconds and in_segment:
                    break

            if in_segment:
                segment_lines.append(line)

        return "\n".join(segment_lines)

    def _timestamp_to_seconds(self, ts: str) -> int:
        """Convert HH:MM:SS to seconds."""
        try:
            parts = ts.split(":")
            if len(parts) == 3:
                h, m, s = parts
                return int(h) * 3600 + int(m) * 60 + int(s)
            elif len(parts) == 2:
                m, s = parts
                return int(m) * 60 + int(s)
        except (ValueError, AttributeError):
            pass
        return 0

    def _aggregate_themes(self, episodes: list[Episode]) -> list[Theme]:
        """Pass 4: Aggregate episodes by theme and generate theme overviews."""
        # Group episodes by theme
        theme_episodes: dict[str, list[Episode]] = {}
        for episode in episodes:
            for theme in episode.key_themes:
                if theme not in theme_episodes:
                    theme_episodes[theme] = []
                theme_episodes[theme].append(episode)

        themes = []
        total_themes = len(theme_episodes)

        for i, (theme_id, eps) in enumerate(theme_episodes.items(), 1):
            print(f"  [{i}/{total_themes}] {theme_id} ({len(eps)} episodes)...", end=" ")

            try:
                # Build episode summaries
                episode_summaries = "\n\n".join([
                    f"- **{e.id}** ({e.guest}): {e.summary}"
                    for e in eps[:20]  # Limit for context
                ])

                # Use GPT-4o for theme aggregation (higher quality)
                prompt = PASS4_THEME_PROMPT.format(
                    theme_name=theme_id.replace("-", " ").title(),
                    episode_summaries=episode_summaries,
                )

                result = self._call_llm(prompt, self.aggregation_model)

                theme = Theme(
                    id=theme_id,
                    name=theme_id.replace("-", " ").title(),
                    description=result.get("description", ""),
                    episode_ids=[e.id for e in eps],
                    subtopics=result.get("subtopics", []),
                    key_episodes=result.get("key_episodes", [])[:5],
                    common_frameworks=result.get("common_frameworks", []),
                )
                themes.append(theme)
                print("OK")

            except Exception as e:
                print(f"ERROR: {e}")

        return themes

    def _build_index(
        self,
        episodes: list[Episode],
        themes: list[Theme],
    ) -> dict:
        """Build the complete index structure."""
        # Build episode index (Level 1)
        episode_index = {}
        for ep in episodes:
            episode_index[ep.id] = {
                "id": ep.id,
                "guest": ep.guest,
                "title": ep.title,
                "publish_date": ep.publish_date,
                "youtube_url": ep.youtube_url,
                "video_id": ep.video_id,
                "duration": ep.duration,
                "summary": ep.summary,
                "key_themes": ep.key_themes,
                "notable_frameworks": ep.notable_frameworks,
                "topic_count": len(ep.topics),
            }

        # Build theme index (Level 2)
        theme_index = {}
        for th in themes:
            theme_index[th.id] = {
                "id": th.id,
                "name": th.name,
                "description": th.description,
                "episode_count": len(th.episode_ids),
                "episodes": th.episode_ids,
                "subtopics": th.subtopics,
                "key_episodes": th.key_episodes,
                "common_frameworks": th.common_frameworks,
            }

        # Build topics index (Level 3)
        topics_index = {}
        for ep in episodes:
            topics_index[ep.id] = [
                {
                    "topic_id": t.topic_id,
                    "title": t.title,
                    "summary": t.summary,
                    "timestamp_start": t.timestamp_start,
                    "timestamp_end": t.timestamp_end,
                    "speakers": t.speakers,
                    "themes": t.themes,
                    "quote_count": len(t.quotes),
                }
                for t in ep.topics
            ]

        # Build quotes index (Level 4)
        quotes_index = {}
        for ep in episodes:
            episode_quotes = []
            for topic in ep.topics:
                for q in topic.quotes:
                    episode_quotes.append({
                        "quote_id": q.quote_id,
                        "topic_id": topic.topic_id,
                        "topic_title": topic.title,
                        "text": q.text,
                        "speaker": q.speaker,
                        "timestamp": q.timestamp,
                        "youtube_link": q.youtube_link,
                        "context": q.context,
                        "insight_type": q.insight_type,
                    })
            if episode_quotes:
                quotes_index[ep.id] = episode_quotes

        return {
            "version": "1.0",
            "generated_at": datetime.now().isoformat(),
            "total_episodes": len(episodes),
            "total_themes": len(themes),
            "levels": {
                "L1": "episode_index",
                "L2": "themes",
                "L3": "topics",
                "L4": "quotes",
            },
            "episode_index": episode_index,
            "themes": theme_index,
            "topics": topics_index,
            "quotes": quotes_index,
        }

    def _save_index(self, index: dict):
        """Save index to files."""
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Save complete index
        with open(self.output_dir / "pageindex.json", "w") as f:
            json.dump(index, f, indent=2)

        # Save episode index separately
        with open(self.output_dir / "episode_index.json", "w") as f:
            json.dump({
                "version": index["version"],
                "generated_at": index["generated_at"],
                "total_episodes": index["total_episodes"],
                "episodes": index["episode_index"],
            }, f, indent=2)

        # Save themes
        themes_dir = self.output_dir / "themes"
        themes_dir.mkdir(exist_ok=True)

        # Theme index file
        with open(themes_dir / "_index.json", "w") as f:
            json.dump({
                "themes": list(index["themes"].keys()),
                "total": len(index["themes"]),
            }, f, indent=2)

        # Individual theme files
        for theme_id, theme_data in index["themes"].items():
            with open(themes_dir / f"{theme_id}.json", "w") as f:
                json.dump(theme_data, f, indent=2)

        # Save topics
        topics_dir = self.output_dir / "topics"
        topics_dir.mkdir(exist_ok=True)

        for episode_id, topics in index["topics"].items():
            with open(topics_dir / f"{episode_id}.json", "w") as f:
                json.dump({"episode_id": episode_id, "topics": topics}, f, indent=2)

        # Save quotes
        quotes_dir = self.output_dir / "quotes"
        quotes_dir.mkdir(exist_ok=True)

        for episode_id, quotes in index["quotes"].items():
            with open(quotes_dir / f"{episode_id}.json", "w") as f:
                json.dump({"episode_id": episode_id, "quotes": quotes}, f, indent=2)

        print(f"\nIndex saved to: {self.output_dir}")
        print(f"  - pageindex.json (complete)")
        print(f"  - episode_index.json")
        print(f"  - themes/ ({len(index['themes'])} files)")
        print(f"  - topics/ ({len(index['topics'])} files)")
        print(f"  - quotes/ ({len(index['quotes'])} files)")

    def _estimate_costs(self, transcripts: list[Path]) -> dict:
        """Estimate API costs without making calls."""
        num_episodes = len(transcripts)

        # Estimate tokens per pass
        pass1_input = num_episodes * 8000  # ~8K tokens per episode excerpt
        pass1_output = num_episodes * 500

        pass2_input = num_episodes * 25000  # ~25K tokens per full transcript
        pass2_output = num_episodes * 1000

        # Estimate ~8 topics per episode
        num_topics = num_episodes * 8
        pass3_input = num_topics * 2000  # ~2K tokens per segment
        pass3_output = num_topics * 500

        # Estimate ~20 themes
        num_themes = 25
        pass4_input = num_themes * 5000  # ~5K tokens per theme aggregation
        pass4_output = num_themes * 500

        # Totals
        total_input = pass1_input + pass2_input + pass3_input + pass4_input
        total_output = pass1_output + pass2_output + pass3_output + pass4_output

        # Costs (GPT-4o-mini for passes 1-3, GPT-4o for pass 4)
        mini_input = pass1_input + pass2_input + pass3_input
        mini_output = pass1_output + pass2_output + pass3_output
        mini_cost = (mini_input / 1_000_000 * 0.15) + (mini_output / 1_000_000 * 0.60)

        gpt4_input = pass4_input
        gpt4_output = pass4_output
        gpt4_cost = (gpt4_input / 1_000_000 * 5) + (gpt4_output / 1_000_000 * 15)

        total_cost = mini_cost + gpt4_cost

        print("\n" + "="*60)
        print("COST ESTIMATE (DRY RUN)")
        print("="*60)
        print(f"\nEpisodes: {num_episodes}")
        print(f"Estimated topics: {num_topics}")
        print(f"Estimated themes: {num_themes}")
        print()
        print("Token estimates:")
        print(f"  Pass 1 (episodes):  {pass1_input:>12,} input, {pass1_output:>10,} output")
        print(f"  Pass 2 (topics):    {pass2_input:>12,} input, {pass2_output:>10,} output")
        print(f"  Pass 3 (quotes):    {pass3_input:>12,} input, {pass3_output:>10,} output")
        print(f"  Pass 4 (themes):    {pass4_input:>12,} input, {pass4_output:>10,} output")
        print(f"  {'─'*55}")
        print(f"  TOTAL:              {total_input:>12,} input, {total_output:>10,} output")
        print()
        print("Cost estimates:")
        print(f"  GPT-4o-mini (passes 1-3): ${mini_cost:>8.2f}")
        print(f"  GPT-4o (pass 4):          ${gpt4_cost:>8.2f}")
        print(f"  {'─'*35}")
        print(f"  TOTAL ESTIMATED COST:     ${total_cost:>8.2f}")
        print()

        return {
            "dry_run": True,
            "episodes": num_episodes,
            "estimated_topics": num_topics,
            "estimated_themes": num_themes,
            "tokens": {
                "total_input": total_input,
                "total_output": total_output,
            },
            "estimated_cost_usd": total_cost,
        }

    def _print_summary(self, index: dict):
        """Print build summary."""
        total_topics = sum(len(t) for t in index["topics"].values())
        total_quotes = sum(len(q) for q in index["quotes"].values())

        print("\n" + "="*60)
        print("PAGEINDEX BUILD COMPLETE")
        print("="*60)
        print(f"\nEpisodes indexed: {index['total_episodes']}")
        print(f"Themes identified: {index['total_themes']}")
        print(f"Topics segmented: {total_topics}")
        print(f"Quotes extracted: {total_quotes}")
        print()
        print("Token usage:")
        print(f"  Input tokens:  {self.token_usage['input_tokens']:>12,}")
        print(f"  Output tokens: {self.token_usage['output_tokens']:>12,}")
        print()


# ============================================================================
# CLI
# ============================================================================

def find_transcripts(directory: Path) -> list[Path]:
    """Find all transcript files in directory."""
    transcripts = []

    for md_file in directory.glob("**/transcript.md"):
        transcripts.append(md_file)

    return sorted(transcripts)


def main():
    parser = argparse.ArgumentParser(
        description="Build PageIndex for Lenny's Podcast transcripts"
    )
    parser.add_argument(
        "--transcripts-dir",
        type=Path,
        help="Directory containing transcript files (e.g., episodes/)",
    )
    parser.add_argument(
        "--file",
        type=Path,
        help="Single transcript file to process",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("./index"),
        help="Output directory for index files (default: ./index)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Estimate costs without making API calls",
    )
    parser.add_argument(
        "--incremental",
        action="store_true",
        help="Only process new episodes not in existing index",
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        default=5,
        help="Max concurrent API calls (default: 5)",
    )

    args = parser.parse_args()

    if not args.transcripts_dir and not args.file:
        parser.error("Either --transcripts-dir or --file must be specified")

    # Collect transcripts
    if args.file:
        if not args.file.exists():
            print(f"Error: File not found: {args.file}")
            sys.exit(1)
        transcripts = [args.file]
    else:
        if not args.transcripts_dir.exists():
            print(f"Error: Directory not found: {args.transcripts_dir}")
            sys.exit(1)
        transcripts = find_transcripts(args.transcripts_dir)

    if not transcripts:
        print("No transcripts found")
        sys.exit(1)

    # Build index
    builder = PageIndexBuilder(
        output_dir=args.output_dir,
        max_workers=args.max_workers,
    )

    builder.build_full_index(
        transcripts=transcripts,
        dry_run=args.dry_run,
        incremental=args.incremental,
    )


if __name__ == "__main__":
    main()
