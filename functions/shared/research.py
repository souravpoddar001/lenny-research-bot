"""
Deep Research Pipeline - 4-stage retrieval and synthesis.

Supports two retrieval modes:
- "vector": Traditional vector search using Azure AI Search (default)
- "pageindex": Reasoning-based retrieval using PageIndex hierarchy

Stages:
1. Query Analysis - Decompose query, identify facets
2. Broad Retrieval - Topic segments for context (vector) OR Theme/Episode navigation (pageindex)
3. Deep Retrieval - Speaker turns for quotes (vector) OR Topic/Quote extraction (pageindex)
4. Synthesis - Generate with citations
"""

import os
import json
import logging
from dataclasses import dataclass, field
from typing import Optional, Literal
from openai import AzureOpenAI

from .search import SearchClient
from .citations import CitationVerifier, Citation

logger = logging.getLogger(__name__)


@dataclass
class QueryPlan:
    """Plan for executing a research query."""
    main_topic: str
    sub_queries: list[str]
    relevant_guests: list[str]
    keywords: list[str]
    output_type: Literal["article", "report", "qa_response"]
    filters: Optional[str] = None


@dataclass
class ResearchOutput:
    """Result of deep research."""
    content: str
    citations: list[Citation]
    sources: list[dict]
    unverified_quotes: list[str] = field(default_factory=list)
    query_plan: Optional[QueryPlan] = None
    executive_summary: Optional[dict] = None

    def to_dict(self) -> dict:
        result = {
            "content": self.content,
            "citations": [c.to_dict() for c in self.citations],
            "sources": self.sources,
            "unverified_quotes": self.unverified_quotes,
        }
        if self.executive_summary:
            result["executive_summary"] = self.executive_summary
        return result


class DeepResearchPipeline:
    """
    4-stage deep research pipeline for comprehensive analysis.

    Usage:
        pipeline = DeepResearchPipeline()
        result = pipeline.research("How do top PMs think about product-market fit?")
    """

    QUERY_ANALYSIS_PROMPT = """You are a research assistant analyzing queries about product leadership and startups.

Analyze the research query and create a retrieval plan.

Output a JSON object with:
- main_topic: Primary topic being researched (string)
- sub_queries: List of 2-4 specific questions to answer (array of strings)
- relevant_guests: Likely podcast guests who discussed this (array of strings, can be empty)
- keywords: Key terms for filtering (array of strings)
- output_type: One of "article", "report", or "qa_response"

For output_type:
- "article": For open-ended questions wanting comprehensive narrative
- "report": For analytical questions wanting structured findings
- "qa_response": For specific factual questions

Example output:
{
    "main_topic": "product-market fit measurement",
    "sub_queries": [
        "What metrics indicate product-market fit?",
        "How do founders know when they have PMF?",
        "What are common mistakes in measuring PMF?"
    ],
    "relevant_guests": ["Rahul Vohra", "Lenny Rachitsky"],
    "keywords": ["product-market fit", "PMF", "retention", "growth"],
    "output_type": "article"
}"""

    SYNTHESIS_PROMPT_ARTICLE = """You are a research assistant writing about product leadership insights from Lenny's Podcast.

Write a comprehensive article based on the provided transcript excerpts. Requirements:

1. CITATION RULES (CRITICAL):
   - Every factual claim must have a citation
   - Use format: — Speaker, "Episode Title" [HH:MM:SS]
   - Direct quotes must be EXACT - copy verbatim from the context
   - DO NOT paraphrase or modify quotes - use the exact words from the source
   - Wrap quotes in quotation marks

2. STRUCTURE:
   - Start with a compelling introduction
   - Organize into logical sections with headers
   - Include specific quotes from guests
   - End with key takeaways

3. STYLE:
   - Professional but accessible
   - Focus on actionable insights
   - Synthesize across multiple sources when relevant

4. EXECUTIVE SUMMARY (REQUIRED):
   After the article, output a JSON block tagged with ```executive_summary

   QUALITY REQUIREMENTS - READ CAREFULLY:

   a) MAIN INSIGHT must be:
      - Self-explanatory: Reader learns something valuable WITHOUT reading the article
      - Specific and surprising, not generic platitudes
      - A complete thought, never truncated
      - BAD: "Great PMs drive clarity and impact" (vague, obvious)
      - BAD: "The key to success is understanding your users and..." (truncated)
      - GOOD: "The best PMs say no to 90% of features—their job is to kill ideas, not add them"
      - GOOD: "Hire for slope over intercept: a fast learner beats an expert every time"

   b) SUPPORTING POINT LABELS must be:
      - Self-explanatory to someone who knows NOTHING about the topic
      - No jargon or undefined terms - if you say "growth model", explain what it does
      - Specific insights that complete "I learned that..."
      - BAD: "Team alignment", "Outcome focus" (buzzwords)
      - BAD: "Use a spreadsheet growth model as common currency" (jargon - what does this mean?)
      - BAD: "Leverage the flywheel effect" (undefined term)
      - GOOD: "Kill features before they kill you"
      - GOOD: "Your first 10 customers will define your entire product direction"
      - GOOD: "Track one metric per growth stage, not dashboards"

   c) KEY QUOTES must be:
      - Complete thoughts that teach something on their own
      - Never fragments or truncated with "..."
      - If a quote is too long, pick a DIFFERENT quote—don't truncate
      - BAD: "So avoid availability or confirmation bias." (fragment, no context)
      - GOOD: "The best product managers I know are the ones who kill the most ideas, not the ones who come up with the most."

   JSON Structure:
   - main_insight: Single most valuable takeaway (80-150 chars, must be complete)
   - supporting_points: Array of 3-4 objects:
     - id: "sp1", "sp2", etc.
     - label: Specific insight headline (5-10 words, completes "I learned that...")
     - description: Why this matters (one sentence)
     - color: Use in order: "#8B5CF6", "#F59E0B", "#10B981", "#3B82F6"
   - key_quotes: Array of 2-3 quotes:
     - text: Complete thought that teaches (60-150 chars, NO truncation)
     - speaker: Speaker name
     - timestamp: HH:MM:SS format
     - youtube_link: Will be filled in by system
     - supports: Which supporting_point id this evidences

Write the article now based on the context provided."""

    SYNTHESIS_PROMPT_REPORT = """You are a research assistant creating a structured report from Lenny's Podcast insights.

Create a research report based on the provided transcript excerpts. Requirements:

1. CITATION RULES (CRITICAL):
   - Every finding must cite its source
   - Use format: — Speaker, "Episode Title" [HH:MM:SS]
   - Direct quotes must be EXACT - copy verbatim from the source
   - DO NOT paraphrase or modify quotes - use the exact words
   - Include a sources section at the end

2. STRUCTURE:
   ## Executive Summary
   (2-3 sentence overview)

   ## Key Findings
   (Numbered findings with citations)

   ## Supporting Evidence
   (Detailed quotes and context)

   ## Implications
   (What this means for practitioners)

3. STYLE:
   - Objective and analytical
   - Evidence-based claims only
   - Clear attribution

4. EXECUTIVE SUMMARY (REQUIRED):
   After the report, output a JSON block tagged with ```executive_summary

   QUALITY REQUIREMENTS - READ CAREFULLY:

   a) MAIN INSIGHT must be:
      - Self-explanatory: Reader learns something valuable WITHOUT reading the report
      - Specific and surprising, not generic platitudes
      - A complete thought, never truncated
      - BAD: "Great PMs drive clarity and impact" (vague, obvious)
      - GOOD: "The best PMs say no to 90% of features—their job is to kill ideas, not add them"

   b) SUPPORTING POINT LABELS must be:
      - Self-explanatory to someone who knows NOTHING about the topic
      - No jargon or undefined terms - if you say "growth model", explain what it does
      - Specific insights that complete "I learned that..."
      - BAD: "Team alignment", "Outcome focus" (buzzwords)
      - BAD: "Use a spreadsheet growth model as common currency" (jargon - what does this mean?)
      - GOOD: "Kill features before they kill you"
      - GOOD: "Track one metric per growth stage, not dashboards"

   c) KEY QUOTES must be:
      - Complete thoughts that teach something on their own
      - Never fragments or truncated with "..."
      - If a quote is too long, pick a DIFFERENT quote—don't truncate

   JSON Structure:
   - main_insight: Single most valuable takeaway (80-150 chars, must be complete)
   - supporting_points: Array of 3-4 objects:
     - id: "sp1", "sp2", etc.
     - label: Specific insight headline (5-10 words, completes "I learned that...")
     - description: Why this matters (one sentence)
     - color: Use in order: "#8B5CF6", "#F59E0B", "#10B981", "#3B82F6"
   - key_quotes: Array of 2-3 quotes:
     - text: Complete thought that teaches (60-150 chars, NO truncation)
     - speaker: Speaker name
     - timestamp: HH:MM:SS format
     - youtube_link: Will be filled in by system
     - supports: Which supporting_point id this evidences

Write the report now based on the context provided."""

    SYNTHESIS_PROMPT_QA = """You are a research assistant answering questions based on Lenny's Podcast transcripts.

Answer the question directly based on the provided transcript excerpts. Requirements:

1. CITATION RULES (CRITICAL):
   - Support your answer with specific quotes
   - Use format: — Speaker, "Episode Title" [HH:MM:SS]
   - Quotes must be EXACT from the context - copy verbatim
   - DO NOT paraphrase or modify quotes - use the exact words

2. STRUCTURE:
   - Start with a direct answer
   - Support with 2-3 relevant quotes
   - Add any important nuances

3. STYLE:
   - Concise but thorough
   - Focus on the specific question asked
   - Acknowledge if information is limited

4. EXECUTIVE SUMMARY (REQUIRED):
   After the answer, output a JSON block tagged with ```executive_summary

   QUALITY REQUIREMENTS - READ CAREFULLY:

   a) MAIN INSIGHT must be:
      - Self-explanatory: Reader learns the answer WITHOUT reading further
      - Specific and direct, not vague
      - A complete thought, never truncated
      - BAD: "PMs should focus on outcomes and..." (truncated, vague)
      - GOOD: "The best PMs say no to 90% of features—their job is to kill ideas, not add them"

   b) SUPPORTING POINT LABELS must be:
      - Self-explanatory to someone who knows NOTHING about the topic
      - No jargon or undefined terms - if you say "growth model", explain what it does
      - Specific insights that complete "I learned that..."
      - BAD: "Team alignment", "Outcome focus" (buzzwords)
      - BAD: "Use a spreadsheet growth model as common currency" (jargon - what does this mean?)
      - GOOD: "Kill features before they kill you"
      - GOOD: "Track one metric per growth stage, not dashboards"

   c) KEY QUOTES must be:
      - Complete thoughts that teach something on their own
      - Never fragments or truncated with "..."
      - If a quote is too long, pick a DIFFERENT quote—don't truncate

   JSON Structure:
   - main_insight: Single most valuable takeaway (80-150 chars, must be complete)
   - supporting_points: Array of 3-4 objects:
     - id: "sp1", "sp2", etc.
     - label: Specific insight headline (5-10 words, completes "I learned that...")
     - description: Why this matters (one sentence)
     - color: Use in order: "#8B5CF6", "#F59E0B", "#10B981", "#3B82F6"
   - key_quotes: Array of 2-3 quotes:
     - text: Complete thought that teaches (60-150 chars, NO truncation)
     - speaker: Speaker name
     - timestamp: HH:MM:SS format
     - youtube_link: Will be filled in by system
     - supports: Which supporting_point id this evidences

Answer the question now based on the context provided."""

    def __init__(
        self,
        search_client: Optional[SearchClient] = None,
        openai_api_key: Optional[str] = None,
        openai_endpoint: Optional[str] = None,
        analysis_model: Optional[str] = None,  # Cost-optimized
        synthesis_model: Optional[str] = None,  # Quality for final output
        retrieval_mode: Literal["vector", "pageindex"] = "vector",
    ):
        """
        Initialize the research pipeline.

        Args:
            search_client: SearchClient for vector mode (created if not provided)
            openai_api_key: Azure OpenAI API key
            openai_endpoint: Azure OpenAI endpoint
            analysis_model: Model for query analysis (uses env var if not provided)
            synthesis_model: Model for final synthesis (uses env var if not provided)
            retrieval_mode: "vector" for Azure AI Search, "pageindex" for reasoning-based
        """
        self.retrieval_mode = retrieval_mode
        self.citation_verifier = CitationVerifier()

        # Initialize retrieval backend based on mode
        if retrieval_mode == "pageindex":
            from .pageindex import PageIndexRetriever
            self.pageindex_retriever = PageIndexRetriever()
            self.search_client = None
            logger.info("Using PageIndex retrieval mode")
        else:
            self.search_client = search_client or SearchClient()
            self.pageindex_retriever = None
            logger.info("Using vector retrieval mode")

        self.openai = AzureOpenAI(
            api_key=openai_api_key or os.environ.get("AZURE_OPENAI_API_KEY"),
            azure_endpoint=openai_endpoint or os.environ.get("AZURE_OPENAI_ENDPOINT"),
            api_version=os.environ.get("AZURE_OPENAI_API_VERSION", "2024-12-01-preview"),
        )

        default_model = os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-5.2")
        self.analysis_model = analysis_model or default_model
        self.synthesis_model = synthesis_model or default_model

    def research(self, query: str) -> ResearchOutput:
        """
        Execute full deep research pipeline.

        Args:
            query: Research query

        Returns:
            ResearchOutput with content, citations, and sources
        """
        # Stage 1: Query Analysis
        plan = self._analyze_query(query)

        # Stage 2 & 3: Retrieval (mode-dependent)
        if self.retrieval_mode == "pageindex":
            # PageIndex reasoning-based retrieval
            retrieval_result = self.pageindex_retriever.retrieve(query)
            chunks = self._convert_pageindex_to_chunks(retrieval_result)
            logger.info(
                f"PageIndex retrieval: {len(chunks)} chunks from "
                f"{retrieval_result.iterations} iteration(s), "
                f"confidence: {retrieval_result.confidence:.0%}"
            )
        else:
            # Vector-based retrieval
            broad_results = self._broad_retrieval(plan)
            chunks = self._deep_retrieval(plan, broad_results)

        # Stage 4: Synthesis
        output = self._synthesize(query, plan, chunks)

        return output

    def _convert_pageindex_to_chunks(self, retrieval_result) -> list[dict]:
        """
        Convert PageIndex retrieval result to chunk format for synthesis.

        The synthesis stage expects chunks with specific fields. This method
        converts PageIndex quotes/topics into that format.
        """
        # Build episode lookup dict for O(1) access
        episode_map = {
            e.get("episode_id") or e.get("id"): e
            for e in retrieval_result.episodes
        }

        chunks = []

        for quote in retrieval_result.quotes:
            # Extract episode_id from quote_id (e.g., "sean-ellis_t1_q1" -> "sean-ellis")
            quote_id = quote.get("quote_id", "")
            episode_id = quote_id.rsplit("_t", 1)[0] if "_t" in quote_id else quote_id.split("_")[0]

            # Find the episode in the results
            episode = episode_map.get(episode_id, {})

            chunk = {
                "content": quote.get("text", ""),
                "speaker": quote.get("speaker", "Unknown"),
                "timestamp_start": quote.get("timestamp", "00:00:00"),
                "title": episode.get("title", "Unknown"),
                "guest": episode.get("guest", "Unknown"),
                "youtube_url": quote.get("youtube_link", episode.get("youtube_url", "")),
                "video_id": episode.get("video_id", ""),
                "transcript_id": episode_id,
                # Additional context from PageIndex
                "topic_title": quote.get("topic_title", ""),
                "topic_summary": quote.get("topic_summary", ""),
                "insight_type": quote.get("insight_type", ""),
                "context": quote.get("context", ""),
            }
            chunks.append(chunk)

        return chunks

    def quick_query(self, query: str) -> ResearchOutput:
        """
        Quick Q&A without full pipeline (cost-optimized).

        Args:
            query: Simple question

        Returns:
            ResearchOutput with answer
        """
        # Single retrieval pass (mode-dependent)
        if self.retrieval_mode == "pageindex":
            # Use quick retrieval for PageIndex
            quotes = self.pageindex_retriever.retrieve_quick(query, top_k=10)

            # Load episode index for metadata lookup
            # Note: load_episode_index() already returns the episodes dict
            episodes = self.pageindex_retriever.index_loader.load_episode_index()

            # Convert to chunk format
            results = []
            for q in quotes:
                # Extract episode_id from quote_id (e.g., "sean-ellis_t1_q1" -> "sean-ellis")
                quote_id = q.get("quote_id", "")
                episode_id = quote_id.rsplit("_t", 1)[0] if "_t" in quote_id else ""
                episode = episodes.get(episode_id, {})

                results.append({
                    "content": q.get("text", ""),
                    "speaker": q.get("speaker", "Unknown"),
                    "timestamp_start": q.get("timestamp", "00:00:00"),
                    "title": episode.get("title", "Unknown"),
                    "guest": episode.get("guest", "Unknown"),
                    "youtube_url": q.get("youtube_link", episode.get("youtube_url", "")),
                    "transcript_id": episode_id,
                })
        else:
            results = self.search_client.hybrid_search(
                query=query,
                top_k=10,
                chunk_type="speaker_turn",
            )

        # Generate with mini model
        context = self._format_context(results)

        response = self.openai.chat.completions.create(
            model=self.analysis_model,  # Use mini for quick queries
            messages=[
                {"role": "system", "content": self.SYNTHESIS_PROMPT_QA},
                {"role": "user", "content": f"Question: {query}\n\nContext:\n{context}"},
            ],
            temperature=0.3,
            max_completion_tokens=1500,
        )

        content = response.choices[0].message.content

        # Verify citations
        fixed_content, citations, unverified = self.citation_verifier.verify_and_fix(
            content, results
        )

        return ResearchOutput(
            content=fixed_content,
            citations=citations,
            sources=self._extract_sources(results),
            unverified_quotes=unverified,
        )

    def _analyze_query(self, query: str) -> QueryPlan:
        """Stage 1: Analyze query and create retrieval plan."""
        response = self.openai.chat.completions.create(
            model=self.analysis_model,
            messages=[
                {"role": "system", "content": self.QUERY_ANALYSIS_PROMPT},
                {"role": "user", "content": f"Research query: {query}"},
            ],
            response_format={"type": "json_object"},
            temperature=0.3,
        )

        plan_data = json.loads(response.choices[0].message.content)

        return QueryPlan(
            main_topic=plan_data.get("main_topic", query),
            sub_queries=plan_data.get("sub_queries", [query]),
            relevant_guests=plan_data.get("relevant_guests", []),
            keywords=plan_data.get("keywords", []),
            output_type=plan_data.get("output_type", "article"),
        )

    def _broad_retrieval(self, plan: QueryPlan) -> list[dict]:
        """Stage 2: Broad retrieval for context."""
        all_results = []
        seen_ids = set()

        # Search for each sub-query
        for sub_query in plan.sub_queries:
            results = self.search_client.hybrid_search(
                query=sub_query,
                top_k=10,
                chunk_type="topic_segment",
                keywords=plan.keywords if plan.keywords else None,
            )

            for r in results:
                if r["id"] not in seen_ids:
                    all_results.append(r)
                    seen_ids.add(r["id"])

        # Also search for specific guests if mentioned
        for guest in plan.relevant_guests[:2]:  # Limit to 2 guests
            results = self.search_client.hybrid_search(
                query=plan.main_topic,
                top_k=5,
                guest=guest,
            )

            for r in results:
                if r["id"] not in seen_ids:
                    all_results.append(r)
                    seen_ids.add(r["id"])

        return all_results[:20]  # Limit total

    def _deep_retrieval(
        self,
        plan: QueryPlan,
        broad_results: list[dict],
    ) -> list[dict]:
        """Stage 3: Deep retrieval for specific quotes."""
        # Get relevant transcript IDs from broad results
        transcript_ids = list(set(r["transcript_id"] for r in broad_results))

        all_results = []
        seen_ids = set()

        # Search within identified transcripts
        for sub_query in plan.sub_queries:
            if transcript_ids:
                # Build filter for relevant transcripts
                transcript_filter = " or ".join(
                    f"transcript_id eq '{tid}'" for tid in transcript_ids[:10]
                )

                results = self.search_client.hybrid_search(
                    query=sub_query,
                    top_k=15,
                    filters=f"({transcript_filter})",
                    chunk_type="speaker_turn",
                )
            else:
                results = self.search_client.hybrid_search(
                    query=sub_query,
                    top_k=15,
                    chunk_type="speaker_turn",
                )

            for r in results:
                if r["id"] not in seen_ids:
                    all_results.append(r)
                    seen_ids.add(r["id"])

        # Rank by relevance score and diversity
        return self._rank_results(all_results)[:30]

    def _rank_results(self, results: list[dict]) -> list[dict]:
        """Rank results by relevance and diversity."""
        # Sort by search score
        sorted_results = sorted(
            results,
            key=lambda x: x.get("@search.reranker_score") or x.get("@search.score", 0),
            reverse=True,
        )

        # Ensure diversity - don't take too many from same transcript
        final_results = []
        transcript_counts = {}

        for r in sorted_results:
            tid = r["transcript_id"]
            count = transcript_counts.get(tid, 0)

            if count < 5:  # Max 5 chunks per transcript
                final_results.append(r)
                transcript_counts[tid] = count + 1

        return final_results

    def _synthesize(
        self,
        query: str,
        plan: QueryPlan,
        chunks: list[dict],
    ) -> ResearchOutput:
        """Stage 4: Synthesize output with citations."""
        # Select appropriate prompt
        if plan.output_type == "report":
            system_prompt = self.SYNTHESIS_PROMPT_REPORT
        elif plan.output_type == "qa_response":
            system_prompt = self.SYNTHESIS_PROMPT_QA
        else:
            system_prompt = self.SYNTHESIS_PROMPT_ARTICLE

        # Format context
        context = self._format_context(chunks)

        # Generate
        response = self.openai.chat.completions.create(
            model=self.synthesis_model,  # Use full model for synthesis
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Research query: {query}\n\nContext from transcripts:\n{context}"},
            ],
            temperature=0.3,
            max_completion_tokens=4000,
        )

        content = response.choices[0].message.content

        # Parse executive summary from response
        content, executive_summary = self._parse_executive_summary(content)

        # Verify and fix citations
        fixed_content, citations, unverified = self.citation_verifier.verify_and_fix(
            content, chunks
        )

        # Update executive summary with youtube links now that we have citations
        if executive_summary:
            citation_map = {c.timestamp: c.to_youtube_link() for c in citations}
            for quote in executive_summary.get('key_quotes', []):
                timestamp = quote.get('timestamp', '')
                if timestamp in citation_map:
                    quote['youtube_link'] = citation_map[timestamp]
                elif not quote.get('youtube_link'):
                    # Try to find by speaker
                    for c in citations:
                        if c.speaker == quote.get('speaker'):
                            quote['youtube_link'] = c.to_youtube_link()
                            break

        # Add sources section
        sources_section = self.citation_verifier.format_citations_section(citations)
        final_content = fixed_content + sources_section

        return ResearchOutput(
            content=final_content,
            citations=citations,
            sources=self._extract_sources(chunks),
            unverified_quotes=unverified,
            query_plan=plan,
            executive_summary=executive_summary,
        )

    def _format_context(self, chunks: list[dict]) -> str:
        """Format chunks as context for LLM."""
        formatted_parts = []

        for chunk in chunks:
            part = f"""---
Source: {chunk.get('title', 'Unknown')}
Guest: {chunk.get('guest', 'Unknown')}
Speaker: {chunk.get('speaker', 'Unknown')}
Timestamp: {chunk.get('timestamp_start', '00:00:00')}

{chunk.get('content', '')}
---"""
            formatted_parts.append(part)

        return "\n\n".join(formatted_parts)

    def _parse_executive_summary(self, content: str) -> tuple[str, Optional[dict]]:
        """
        Parse executive summary JSON from LLM response.

        Returns:
            Tuple of (content_without_json, executive_summary_dict)
        """
        import re

        # Look for ```executive_summary or ```json tagged block
        pattern = r'```(?:executive_summary|json)\s*(\{[\s\S]*?\})\s*```'
        match = re.search(pattern, content)

        if not match:
            return content, None

        # Extract JSON and clean content
        json_str = match.group(1)
        clean_content = content[:match.start()].rstrip()

        try:
            summary = json.loads(json_str)
            return clean_content, summary
        except json.JSONDecodeError:
            logger.warning("Failed to parse executive summary JSON")
            return content, None

    def _extract_sources(self, chunks: list[dict]) -> list[dict]:
        """Extract unique sources from chunks."""
        sources = {}

        for chunk in chunks:
            tid = chunk.get("transcript_id")
            if tid and tid not in sources:
                sources[tid] = {
                    "transcript_id": tid,
                    "title": chunk.get("title"),
                    "guest": chunk.get("guest"),
                    "youtube_url": chunk.get("youtube_url"),
                }

        return list(sources.values())
