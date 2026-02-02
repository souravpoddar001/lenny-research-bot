"""
Navigation prompts for PageIndex retrieval.

These prompts guide the LLM through the hierarchical index structure
to find relevant content for user queries.
"""

# Speaker Extraction Prompt (Pre-Navigation)
SPEAKER_EXTRACTION_PROMPT = """Extract any named speaker/guest from this podcast research query.

QUERY: {query}

Your task: Identify if the query mentions a specific person by name whose views are being requested.

Output JSON:
{{
  "named_speaker": "Speaker name if explicitly mentioned, or null",
  "is_speaker_specific": true or false
}}

Examples:
- "What does Sean Ellis say about PMF?" -> {{"named_speaker": "Sean Ellis", "is_speaker_specific": true}}
- "What is product-market fit?" -> {{"named_speaker": null, "is_speaker_specific": false}}
- "Tell me about Rahul's thoughts on growth" -> {{"named_speaker": "Rahul", "is_speaker_specific": true}}
- "How do top PMs approach roadmapping?" -> {{"named_speaker": null, "is_speaker_specific": false}}
- "What did the Airbnb founder say about culture?" -> {{"named_speaker": "Brian Chesky", "is_speaker_specific": true}}

IMPORTANT: Only set is_speaker_specific to true if a specific person's name is mentioned."""


# Theme Selection Prompt (Level 2 Navigation)
THEME_SELECTION_PROMPT = """You are navigating a research index to answer a user query about product, growth, and startup topics from Lenny's Podcast.

USER QUERY: {query}

AVAILABLE THEMES (these are the ONLY valid theme IDs you can select):
{theme_list}

Your task: Select 1-3 themes most likely to contain relevant information for this query.

CRITICAL RULES:
1. ONLY select theme IDs from the AVAILABLE THEMES list above
2. Do NOT invent, guess, or create theme IDs
3. Copy theme IDs exactly as shown (e.g., "product-market-fit" not "pmf" or "PMF")
4. If no available themes match well, select the closest relevant ones

Think through:
1. What is the user really asking about?
2. Which AVAILABLE THEMES directly address this topic?
3. Are there related themes that might have supporting information?

Output JSON:
{{
  "selected_themes": ["theme-id-1", "theme-id-2"],
  "reasoning": "Brief explanation of why these themes are relevant to the query"
}}

IMPORTANT: Only select themes that are genuinely relevant. If the query is very specific, 1 theme may be sufficient."""


# Episode Selection Prompt (Level 1 Navigation within themes)
EPISODE_SELECTION_PROMPT = """You are selecting podcast episodes to find answers to a user query.

USER QUERY: {query}

NAMED SPEAKER (if query asks about a specific person): {named_speaker}

SELECTED THEMES: {themes}

EPISODES IN THESE THEMES:
{episode_summaries}

Your task: Select 2-5 episodes most likely to contain valuable insights for this query.

SPEAKER PRIORITY RULES (CRITICAL):
- If NAMED SPEAKER is specified (not "None"), ALWAYS include episodes with that guest FIRST
- If the named speaker matches a guest name, that episode MUST be in your selection
- Only add other episodes after including all matches for the named speaker

Consider:
1. Guest match - if a named speaker is specified, prioritize their episodes
2. Guest expertise - who would know most about this topic?
3. Episode summary - does it mention relevant concepts?
4. Frameworks mentioned - do any directly address the query?
5. Diversity - if no named speaker, include perspectives from different guests

Output JSON:
{{
  "selected_episodes": ["episode-id-1", "episode-id-2", "episode-id-3"],
  "speaker_matched": true or false,
  "reasoning": "Brief explanation of why these episodes are most relevant"
}}

IMPORTANT: If a named speaker is specified, you MUST include their episode(s) even if other episodes seem more topically relevant."""


# Topic Selection Prompt (Level 3 Navigation)
TOPIC_SELECTION_PROMPT = """You are selecting specific discussion topics from podcast episodes to answer a user query.

USER QUERY: {query}

TOPICS FROM SELECTED EPISODES:
{topic_list}

Your task: Select 3-8 topics most likely to contain the specific information needed.

Consider:
1. Topic title and summary - does it directly address the query?
2. Timestamp ranges - longer topics often have more depth
3. Speakers involved - guest expertise matters
4. Theme relevance - topics tagged with relevant themes

Output JSON:
{{
  "selected_topics": ["topic-id-1", "topic-id-2", "topic-id-3"],
  "reasoning": "Brief explanation of why these topics are most relevant"
}}

IMPORTANT: Select topics that will provide specific, actionable insights - not just general mentions of the topic."""


# Sufficiency Assessment Prompt
SUFFICIENCY_PROMPT = """You are assessing whether enough information has been retrieved to answer a user query.

USER QUERY: {query}

RETRIEVED QUOTES AND CONTEXT:
{quotes_context}

Assess:
1. Can the query be answered with the information above?
2. What aspects of the query (if any) remain unanswered?
3. Would exploring additional themes help?

Output JSON:
{{
  "sufficient": true or false,
  "confidence": 0.0 to 1.0,
  "answered_aspects": ["What parts of the query can be answered"],
  "missing_aspects": ["What parts still need information"],
  "suggested_themes": ["Additional themes to explore if not sufficient"]
}}

Be conservative - if the quotes provide good coverage with multiple perspectives, mark as sufficient.
Only suggest additional themes if there's a clear gap in the retrieved information."""


# Quote Relevance Scoring Prompt
QUOTE_RELEVANCE_PROMPT = """You are scoring the relevance of quotes to a user query.

USER QUERY: {query}

QUOTES:
{quotes}

For each quote, assess its relevance to the query on a scale of 0-10:
- 10: Directly answers the query with specific actionable insight
- 7-9: Highly relevant, provides valuable related information
- 4-6: Somewhat relevant, provides context or background
- 1-3: Tangentially related
- 0: Not relevant

Output JSON:
{{
  "scored_quotes": [
    {{
      "quote_id": "...",
      "relevance_score": 8,
      "relevance_reason": "Brief explanation"
    }}
  ]
}}"""


# Context Building Prompt (for synthesis preparation)
CONTEXT_BUILDING_PROMPT = """You are preparing context from podcast quotes to answer a user query.

USER QUERY: {query}

RETRIEVED QUOTES (sorted by relevance):
{quotes}

Your task: Organize these quotes into a coherent context that will help answer the query.

Group quotes by:
1. Main insights that directly answer the query
2. Supporting evidence and examples
3. Contrasting or nuanced perspectives
4. Practical advice and actionable takeaways

Output the quotes in this organized structure with headers, maintaining exact quote text and attribution.

Format:
## Main Insights
[Most directly relevant quotes]

## Supporting Evidence
[Quotes that provide evidence, examples, or case studies]

## Nuances and Considerations
[Quotes that add important caveats or alternative perspectives]

## Actionable Takeaways
[Quotes with specific, practical advice]"""
