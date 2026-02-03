"""
PageIndex: LLM Reasoning-Based Retrieval (Primary Retrieval System)

This is the default retrieval system for Lenny's Research Bot. Instead of
using vector embeddings and similarity search, PageIndex uses an LLM to
reason through a hierarchical index structure to find relevant content.

Navigation Flow:
1. Extract named speaker from query (if asking about specific guest)
2. Select relevant themes from index
3. Select relevant episodes within themes
4. Select relevant topics within episodes
5. Retrieve quotes from topics
6. Assess sufficiency, loop if needed

Benefits over vector search:
- No vector database infrastructure needed (~$73/month saved)
- No embedding API calls required
- Explainable retrieval (reasoning trace shows navigation decisions)
- Better handling of conceptual queries
- Speaker-aware navigation
"""

import os
import json
import logging
from dataclasses import dataclass, field
from typing import Optional, Literal

from openai import AzureOpenAI

from .index_loader import IndexLoader
from .prompts import (
    SPEAKER_EXTRACTION_PROMPT,
    THEME_SELECTION_PROMPT,
    EPISODE_SELECTION_PROMPT,
    TOPIC_SELECTION_PROMPT,
    SUFFICIENCY_PROMPT,
)

logger = logging.getLogger(__name__)


@dataclass
class NavigationState:
    """Tracks the current state of index navigation."""
    current_level: Literal["themes", "episodes", "topics", "quotes"]
    selected_themes: list[str] = field(default_factory=list)
    selected_episodes: list[str] = field(default_factory=list)
    selected_topics: list[str] = field(default_factory=list)
    retrieved_quotes: list[dict] = field(default_factory=list)
    iteration: int = 0
    reasoning_trace: list[str] = field(default_factory=list)
    named_speaker: Optional[str] = None  # Speaker extracted from query

    def add_trace(self, step: str, reasoning: str):
        """Add a step to the reasoning trace."""
        self.reasoning_trace.append(f"[{step}] {reasoning}")


@dataclass
class RetrievalResult:
    """Result of PageIndex retrieval."""
    quotes: list[dict]
    topics: list[dict]
    episodes: list[dict]
    themes: list[str]
    reasoning_trace: list[str]
    iterations: int
    sufficient: bool
    confidence: float


class PageIndexRetriever:
    """
    Reasoning-based retrieval through the PageIndex hierarchy.

    Unlike vector search which finds similar embeddings, this retriever
    uses an LLM to reason through the index structure and select
    relevant content based on semantic understanding.

    Usage:
        retriever = PageIndexRetriever()
        result = retriever.retrieve("How do I know if I have product-market fit?")

        # Access retrieved content
        for quote in result.quotes:
            print(f"{quote['speaker']}: {quote['text']}")

        # See how the system found this content
        for step in result.reasoning_trace:
            print(step)
    """

    MAX_ITERATIONS = 3
    MAX_QUOTES_PER_TOPIC = 5
    MAX_TOTAL_QUOTES = 30

    def __init__(
        self,
        index_loader: Optional[IndexLoader] = None,
        openai_api_key: Optional[str] = None,
        openai_endpoint: Optional[str] = None,
        navigation_model: Optional[str] = None,
    ):
        """
        Initialize the retriever.

        Args:
            index_loader: IndexLoader instance (creates default if not provided)
            openai_api_key: Azure OpenAI API key (uses env var if not provided)
            openai_endpoint: Azure OpenAI endpoint (uses env var if not provided)
            navigation_model: Model to use for navigation decisions (uses env var if not provided)
        """
        self.index_loader = index_loader or IndexLoader()

        self.openai = AzureOpenAI(
            api_key=openai_api_key or os.environ.get("AZURE_OPENAI_API_KEY"),
            azure_endpoint=openai_endpoint or os.environ.get("AZURE_OPENAI_ENDPOINT"),
            api_version=os.environ.get("AZURE_OPENAI_API_VERSION", "2024-12-01-preview"),
        )

        self.navigation_model = navigation_model or os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-5.2")

    def _extract_named_speaker(self, query: str) -> Optional[str]:
        """Extract named speaker from query if present."""
        prompt = SPEAKER_EXTRACTION_PROMPT.format(query=query)
        try:
            result = self._call_llm(prompt)
            if result.get("is_speaker_specific"):
                speaker = result.get("named_speaker")
                logger.info(f"Extracted named speaker from query: {speaker}")
                return speaker
        except Exception as e:
            logger.warning(f"Error extracting speaker: {e}")
        return None

    def retrieve(self, query: str) -> RetrievalResult:
        """
        Retrieve relevant content for a query using reasoning-based navigation.

        Args:
            query: User's research query

        Returns:
            RetrievalResult with quotes, topics, episodes, and reasoning trace
        """
        state = NavigationState(current_level="themes")

        # Extract named speaker from query (e.g., "What does Sean Ellis say...")
        state.named_speaker = self._extract_named_speaker(query)
        if state.named_speaker:
            state.add_trace("Speaker", f"Query asks about specific speaker: {state.named_speaker}")

        while state.iteration < self.MAX_ITERATIONS:
            logger.info(f"Retrieval iteration {state.iteration + 1}")

            # Step 1: Select themes
            if not state.selected_themes or state.iteration > 0:
                state = self._select_themes(query, state)

            # Step 2: Select episodes within themes
            state = self._select_episodes(query, state)

            # Step 3: Select topics within episodes
            state = self._select_topics(query, state)

            # Step 4: Retrieve quotes from topics
            state = self._retrieve_quotes(state)

            # Step 5: Assess sufficiency
            is_sufficient, confidence, suggested_themes = self._assess_sufficiency(
                query, state
            )

            if is_sufficient or state.iteration >= self.MAX_ITERATIONS - 1:
                state.add_trace(
                    "Complete",
                    f"Retrieval complete after {state.iteration + 1} iteration(s). "
                    f"Confidence: {confidence:.0%}"
                )
                return self._build_result(state, is_sufficient, confidence)

            # Not sufficient - add suggested themes for next iteration
            state.add_trace(
                "Expanding",
                f"Insufficient coverage (confidence: {confidence:.0%}). "
                f"Exploring additional themes: {suggested_themes}"
            )
            state.selected_themes.extend(
                t for t in suggested_themes if t not in state.selected_themes
            )
            state.iteration += 1

        return self._build_result(state, False, 0.5)

    def _call_llm(self, prompt: str) -> dict:
        """Make LLM call and parse JSON response."""
        response = self.openai.chat.completions.create(
            model=self.navigation_model,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.3,
            max_completion_tokens=2000,
        )
        return json.loads(response.choices[0].message.content)

    def _select_themes(self, query: str, state: NavigationState) -> NavigationState:
        """Step 1: Select relevant themes based on query."""
        # Load all themes
        themes = self.index_loader.load_all_themes()

        # Format theme list for prompt
        theme_list = "\n".join([
            f"- **{tid}**: {t.get('description', 'No description')} "
            f"({t.get('episode_count', 0)} episodes)"
            for tid, t in themes.items()
        ])

        prompt = THEME_SELECTION_PROMPT.format(
            query=query,
            theme_list=theme_list,
        )

        result = self._call_llm(prompt)
        selected = result.get("selected_themes", [])
        reasoning = result.get("reasoning", "")

        # Validate themes exist
        valid_themes = [t for t in selected if t in themes]

        # Log warning if hallucination detected
        if len(selected) > len(valid_themes):
            hallucinated = [t for t in selected if t not in themes]
            logger.warning(f"Theme hallucination detected: {hallucinated} not in index")

        state.selected_themes = list(set(state.selected_themes + valid_themes))
        state.current_level = "episodes"
        state.add_trace("Themes", f"Selected {valid_themes}. {reasoning}")

        return state

    def _select_episodes(self, query: str, state: NavigationState) -> NavigationState:
        """Step 2: Select relevant episodes from selected themes."""
        episodes = self.index_loader.load_episode_index()

        # Get episodes for selected themes
        theme_episodes = set()
        for theme_id in state.selected_themes:
            try:
                theme = self.index_loader.load_theme(theme_id)
                theme_episodes.update(theme.get("episodes", []))
            except FileNotFoundError:
                continue

        # If named_speaker specified, find matching episodes and prioritize them
        speaker_matched_eps = []
        other_eps = []

        if state.named_speaker:
            speaker_lower = state.named_speaker.lower()
            for ep_id in theme_episodes:
                if ep_id in episodes:
                    ep = episodes[ep_id]
                    guest = ep.get('guest', '').lower()
                    # Check if speaker name matches guest name
                    if speaker_lower in guest or guest in speaker_lower:
                        speaker_matched_eps.append(ep_id)
                    else:
                        other_eps.append(ep_id)

            # Also search all episodes (not just theme episodes) if no match found
            if not speaker_matched_eps:
                for ep_id, ep in episodes.items():
                    guest = ep.get('guest', '').lower()
                    if speaker_lower in guest or guest in speaker_lower:
                        speaker_matched_eps.append(ep_id)
                        # Add to theme_episodes so it's included
                        theme_episodes.add(ep_id)

            logger.info(f"Speaker match for '{state.named_speaker}': {speaker_matched_eps}")
        else:
            other_eps = list(theme_episodes)

        # Order: speaker matches first, then others
        ordered_eps = speaker_matched_eps + other_eps

        # Format episode summaries (speaker matches always included first)
        episode_summaries = []
        for ep_id in ordered_eps:
            if ep_id in episodes:
                ep = episodes[ep_id]
                episode_summaries.append(
                    f"- **{ep_id}** ({ep.get('guest', 'Unknown')}): "
                    f"{ep.get('summary', 'No summary')[:200]}... "
                    f"[Frameworks: {', '.join(ep.get('notable_frameworks', [])[:3])}]"
                )

        prompt = EPISODE_SELECTION_PROMPT.format(
            query=query,
            named_speaker=state.named_speaker or "None",
            themes=", ".join(state.selected_themes),
            episode_summaries="\n".join(episode_summaries[:30]),  # Limit for context
        )

        result = self._call_llm(prompt)
        selected = result.get("selected_episodes", [])
        reasoning = result.get("reasoning", "")

        # Validate episodes exist
        valid_episodes = [e for e in selected if e in episodes]

        state.selected_episodes = list(set(state.selected_episodes + valid_episodes))
        state.current_level = "topics"
        state.add_trace("Episodes", f"Selected {valid_episodes}. {reasoning}")

        return state

    def _select_topics(self, query: str, state: NavigationState) -> NavigationState:
        """Step 3: Select relevant topics from selected episodes."""
        # Gather all topics from selected episodes
        all_topics = []
        for ep_id in state.selected_episodes:
            topics = self.index_loader.load_topics(ep_id)
            episodes = self.index_loader.load_episode_index()
            ep = episodes.get(ep_id, {})

            for t in topics:
                all_topics.append({
                    **t,
                    "episode_id": ep_id,
                    "guest": ep.get("guest", "Unknown"),
                })

        # Format topic list
        topic_list = "\n".join([
            f"- **{t['topic_id']}** ({t['guest']}): {t['title']}\n"
            f"  Summary: {t['summary'][:150]}... "
            f"[{t['timestamp_start']} - {t['timestamp_end']}]"
            for t in all_topics
        ])

        prompt = TOPIC_SELECTION_PROMPT.format(
            query=query,
            topic_list=topic_list[:15000],  # Limit for context
        )

        result = self._call_llm(prompt)
        selected = result.get("selected_topics", [])
        reasoning = result.get("reasoning", "")

        # Validate topics exist
        valid_topic_ids = {t["topic_id"] for t in all_topics}
        valid_topics = [t for t in selected if t in valid_topic_ids]

        state.selected_topics = list(set(state.selected_topics + valid_topics))
        state.current_level = "quotes"
        state.add_trace("Topics", f"Selected {len(valid_topics)} topics. {reasoning}")

        return state

    def _retrieve_quotes(self, state: NavigationState) -> NavigationState:
        """Step 4: Retrieve quotes from selected topics."""
        all_quotes = []

        for topic_id in state.selected_topics:
            quotes = self.index_loader.load_quotes_for_topic(topic_id)

            # Get topic context
            parts = topic_id.rsplit("_t", 1)
            if len(parts) == 2:
                ep_id = parts[0]
                topics = self.index_loader.load_topics(ep_id)
                topic_info = next(
                    (t for t in topics if t["topic_id"] == topic_id),
                    {}
                )

                # Add topic context to quotes
                for q in quotes[:self.MAX_QUOTES_PER_TOPIC]:
                    q["topic_title"] = topic_info.get("title", "")
                    q["topic_summary"] = topic_info.get("summary", "")
                    all_quotes.append(q)

        # Limit total quotes
        state.retrieved_quotes = all_quotes[:self.MAX_TOTAL_QUOTES]
        state.add_trace(
            "Quotes",
            f"Retrieved {len(state.retrieved_quotes)} quotes from "
            f"{len(state.selected_topics)} topics"
        )

        return state

    def _assess_sufficiency(
        self,
        query: str,
        state: NavigationState,
    ) -> tuple[bool, float, list[str]]:
        """Step 5: Assess if retrieved content is sufficient."""
        if not state.retrieved_quotes:
            return False, 0.0, state.selected_themes

        # Format quotes for assessment
        quotes_context = "\n\n".join([
            f"**{q.get('speaker', 'Unknown')}** ({q.get('topic_title', '')})\n"
            f"> \"{q.get('text', '')}\"\n"
            f"Context: {q.get('context', '')}"
            for q in state.retrieved_quotes[:20]
        ])

        prompt = SUFFICIENCY_PROMPT.format(
            query=query,
            quotes_context=quotes_context,
        )

        result = self._call_llm(prompt)

        is_sufficient = result.get("sufficient", False)
        base_confidence = result.get("confidence", 0.5)
        suggested_themes = result.get("suggested_themes", [])

        # Adjust confidence based on quote count and theme coverage
        # This prevents unnecessary iterations when we have good coverage
        quote_bonus = min(0.3, len(state.retrieved_quotes) * 0.01)  # Up to 0.3 for 30+ quotes
        theme_bonus = min(0.2, len(state.selected_themes) * 0.1)   # Up to 0.2 for 2+ themes
        confidence = min(1.0, base_confidence + quote_bonus + theme_bonus)

        return is_sufficient, confidence, suggested_themes

    def _build_result(
        self,
        state: NavigationState,
        sufficient: bool,
        confidence: float,
    ) -> RetrievalResult:
        """Build final retrieval result."""
        # Deduplicate quotes by quote_id
        seen_quotes = set()
        unique_quotes = []
        for quote in state.retrieved_quotes:
            quote_id = quote.get("quote_id")
            if quote_id and quote_id not in seen_quotes:
                seen_quotes.add(quote_id)
                unique_quotes.append(quote)

        # Get full topic and episode details
        episodes = self.index_loader.load_episode_index()

        topic_details = []
        for topic_id in state.selected_topics:
            parts = topic_id.rsplit("_t", 1)
            if len(parts) == 2:
                ep_id = parts[0]
                topics = self.index_loader.load_topics(ep_id)
                topic = next((t for t in topics if t["topic_id"] == topic_id), None)
                if topic:
                    topic_details.append({
                        **topic,
                        "episode_id": ep_id,
                        "guest": episodes.get(ep_id, {}).get("guest", "Unknown"),
                        "title": episodes.get(ep_id, {}).get("title", "Unknown"),
                    })

        episode_details = [
            episodes[ep_id]
            for ep_id in state.selected_episodes
            if ep_id in episodes
        ]

        return RetrievalResult(
            quotes=unique_quotes,
            topics=topic_details,
            episodes=episode_details,
            themes=state.selected_themes,
            reasoning_trace=state.reasoning_trace,
            iterations=state.iteration + 1,
            sufficient=sufficient,
            confidence=confidence,
        )

    def retrieve_quick(self, query: str, top_k: int = 10) -> list[dict]:
        """
        Quick retrieval without full reasoning (for simple queries).

        Does a single pass through themes → episodes → topics → quotes
        without sufficiency assessment or iteration.

        Args:
            query: User query
            top_k: Maximum quotes to return

        Returns:
            List of quote dicts
        """
        state = NavigationState(current_level="themes")

        # Single pass through hierarchy
        state = self._select_themes(query, state)
        state = self._select_episodes(query, state)
        state = self._select_topics(query, state)
        state = self._retrieve_quotes(state)

        return state.retrieved_quotes[:top_k]
