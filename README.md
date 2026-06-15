# FitFindr

FitFindr is an outfit assistant for secondhand shopping. It searches a local listings dataset, suggests how to style the best match with a user wardrobe, and generates a social-ready fit card caption.

## Setup

1. Create and activate a virtual environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Add your Groq key in .env:

```env
GROQ_API_KEY=your_key_here
```

4. Run tests:

```bash
pytest tests
```

5. Run the app:

```bash
python app.py
```

## Tool Inventory

### Tool: search_listings

Purpose:
Find and rank listing matches for a user request.

Inputs:
- description (str): item query text, for example vintage graphic tee.
- size (str | None): optional size filter, for example M or US 7.
- max_price (float | None): optional maximum price filter.

Output:
- list[dict]: ranked listing dictionaries. Each item includes id, title, description, category, style_tags, size, condition, price, colors, brand, and platform.

### Tool: suggest_outfit

Purpose:
Generate styling advice for a selected listing, using wardrobe items when available.

Inputs:
- new_item (dict): selected listing dictionary from search_listings.
- wardrobe (dict): wardrobe object with items list following data/wardrobe_schema.json.

Output:
- str: non-empty outfit guidance. If wardrobe is empty, returns general styling advice.

### Tool: create_fit_card

Purpose:
Convert outfit guidance and selected listing into a short social caption.

Inputs:
- outfit (str): suggestion text from suggest_outfit.
- new_item (dict): selected listing dictionary with title, price, platform, etc.

Output:
- str: 2 to 4 sentence fit card caption. If outfit is empty, returns an error message string.

## Planning Loop

The agent follows a fixed, conditional sequence:

1. Parse query into description, size, and max_price.
2. Call search_listings(description, size, max_price).
3. If search results are empty, set session error and return early.
4. Set selected_item = search_results[0].
5. Call suggest_outfit(selected_item, wardrobe).
6. If outfit text is empty, set session error and return early.
7. Call create_fit_card(outfit_suggestion, selected_item).
8. If fit card is empty, set session error and return early.
9. Return final session.

This means tools are not called unconditionally. The no-results branch exits before outfit and fit-card generation.

## State Management

State is stored in a per-request session dictionary in agent.py:

- query: original user query
- parsed: extracted description, size, max_price
- search_results: ranked list from search_listings
- selected_item: the top listing passed to suggest_outfit
- wardrobe: selected wardrobe payload
- outfit_suggestion: string passed to create_fit_card
- fit_card: final caption
- error: early-exit message for failure paths

State handoff behavior:
- selected_item is taken directly from search_results[0] and passed into suggest_outfit.
- outfit_suggestion is passed directly into create_fit_card.
- app.py reads session and maps it to UI panels.

## Error Handling

### search_listings no results

Behavior:
Returns empty list, not an exception.

Concrete test example:

```bash
python -c "from tools import search_listings; print(search_listings('designer ballgown', size='XXS', max_price=5))"
```

Observed output:
- []

Agent response:
- No listings matched that search. Try removing the size filter, widening the price range, or using broader keywords.

### suggest_outfit with empty wardrobe

Behavior:
Returns general styling advice instead of crashing. If LLM call is unavailable, returns a fallback advice string.

Concrete test example:

```bash
python -c "from tools import search_listings, suggest_outfit; from utils.data_loader import get_empty_wardrobe; results = search_listings('vintage graphic tee', size=None, max_price=50); print(suggest_outfit(results[0], get_empty_wardrobe()))"
```

Observed output:
- Non-empty advice string.

### create_fit_card with missing outfit text

Behavior:
Returns a descriptive error string instead of an exception.

Concrete test example:

```bash
python -c "from tools import search_listings, create_fit_card; results = search_listings('vintage graphic tee', size=None, max_price=50); print(create_fit_card('', results[0]))"
```

Observed output:
- Error: outfit suggestion is missing, so I can't create a fit card.

## AI Usage

### Instance 1: Tool implementation in tools.py

AI input provided:
- planning.md Tool 1, Tool 2, Tool 3 specs
- required model and constraints from docstrings in tools.py
- architecture expectations from planning.md

AI output produced:
- initial implementations for search_listings, suggest_outfit, and create_fit_card

What I changed before using:
- tightened search ranking and filtering behavior to match the exact parameter semantics
- added safe fallbacks for suggest_outfit and create_fit_card when GROQ_API_KEY or LLM call is unavailable
- kept create_fit_card empty-outfit guard returning string errors

### Instance 2: Planning loop wiring in agent.py and app.py

AI input provided:
- planning.md sections: Planning Loop, State Management, Error Handling
- planning.md Architecture diagram
- agent.py and app.py TODO step lists

AI output produced:
- run_agent implementation with parse, branch, and session updates
- handle_query implementation mapping session fields to UI outputs

What I changed before using:
- ensured early return is triggered on empty search_results
- confirmed selected_item and outfit_suggestion are passed forward from session state
- validated no-results path leaves fit_card as None and does not call downstream tools

## Spec Reflection

One way the spec helped:
Writing the planning loop section of planning.md before touching agent.py forced an explicit early-exit decision on empty search results. Without that written constraint, it would have been easy to pass an empty list straight into suggest_outfit and only discover the bug at runtime. The spec made the branch visible before any code existed.

One way implementation diverged from the spec and why:
The original spec assumed the LLM would always be available. In practice, running tests without a configured GROQ_API_KEY caused suggest_outfit and create_fit_card to raise exceptions instead of returning strings. The implementation was updated to catch LLM call failures and return fallback advice strings, keeping the agent functional even without a live API key. This was not in the original spec but was necessary for the agent to be reliably testable and demonstrable.

## Demo Video Checklist (3 to 5 minutes)

Use this structure while recording:

1. Show app startup with python app.py and open the local URL.
2. Run one full happy-path query using all 3 tools, for example vintage graphic tee under 30.
3. Narrate state flow:
- selected_item is chosen from search_results[0]
- outfit_suggestion is generated from selected_item and wardrobe
- fit_card is generated from outfit_suggestion and selected_item
4. Trigger one failure path live:
- impossible query no-results branch, or
- create_fit_card with empty outfit string
5. Show graceful response text and explain why this proves error handling works.

Suggested terminal commands for failure demo:

```bash
python -c "from tools import search_listings; print(search_listings('designer ballgown', size='XXS', max_price=5))"
python -c "from agent import run_agent; from utils.data_loader import get_example_wardrobe; s = run_agent('designer ballgown size XXS under $5', get_example_wardrobe()); print(s['error']); print(s['fit_card'])"
```
