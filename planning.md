# FitFindr — planning.md

> Complete this document before writing any implementation code.
> Your spec and agent diagram are what you'll use to direct AI tools (Claude, Copilot, etc.) to generate your implementation — the more specific they are, the more useful the generated code will be.
> Your planning.md will be reviewed as part of your submission.
> Update it before starting any stretch features.

---

## Tools

List every tool your agent will use. For each tool, fill in all four fields.
You must have at least 3 tools. The three required tools are listed — add any additional tools below them.

### Tool 1: search_listings

**What it does:**
Searches the mock secondhand listings dataset for items that match the user's request. It filters by the requested description keywords, optional size, and optional maximum price, then ranks the remaining items so the best match appears first.

**Input parameters:**
<!-- List each parameter, its type, and what it represents -->
- `description` (str): The item the user wants, such as "vintage graphic tee" or "90s track jacket". The tool uses this text to score keyword overlap against each listing's title, description, category, style_tags, colors, and brand.
- `size` (str | None): Optional size filter from the user's query, such as "M", "size 8", or "W30 L30". The tool keeps listings whose size field matches the requested size in a case-insensitive way or clearly contains the requested value.
- `max_price` (float | None): Optional maximum price the user is willing to pay. The tool keeps only listings with price less than or equal to this value.

**What it returns:**
A list of listing dictionaries sorted from most relevant to least relevant. Each dictionary includes `id`, `title`, `description`, `category`, `style_tags`, `size`, `condition`, `price`, `colors`, `brand`, and `platform`, so the next tool can choose one listing and present it to the user.

**What happens if it fails or returns nothing:**
If no listings match all filters, the agent stops immediately, sets a helpful error message in session state, and tells the user to broaden the search, remove the size filter, or raise the budget. It does not call `suggest_outfit` or `create_fit_card` with an empty result.

---

### Tool 2: suggest_outfit

**What it does:**
Builds 1–2 outfit ideas that center the selected new item and use pieces from the user's wardrobe when possible. It should name specific wardrobe items, explain the overall vibe, and include at least one practical styling note such as layering, tucking, rolling sleeves, or footwear pairing.

**Input parameters:**
<!-- List each parameter, its type, and what it represents -->
- `new_item` (dict): The listing dictionary chosen from `search_listings`. It contains the item title, category, colors, style tags, price, platform, and other listing details the outfit generator should reference.
- `wardrobe` (dict): A wardrobe dictionary in the schema from `wardrobe_schema.json`, with an `items` list of closet pieces. Each item has `id`, `name`, `category`, `colors`, `style_tags`, and optional `notes`.

**What it returns:**
A non-empty styling paragraph or short list of outfit ideas. The response should clearly connect the thrifted item to one or more wardrobe pieces and explain why the combination works.

**What happens if it fails or returns nothing:**
If the wardrobe is empty, the tool should still return general styling advice for the new item instead of failing, and the agent should keep going. If the tool returns an empty string or clearly unusable output, the agent should set an error message that says it could not generate styling advice and stop before creating a fit card.

---

### Tool 3: create_fit_card

**What it does:**
Turns the selected item and outfit idea into a short social caption that sounds like a real outfit post. It should mention the item name, price, and platform naturally, and keep the tone casual, specific, and shareable.

**Input parameters:**
<!-- List each parameter, its type, and what it represents -->
- `outfit` (str): The styling text returned by `suggest_outfit`, including the outfit combination and vibe.
- `new_item` (dict): The selected listing dictionary so the caption can mention the item's name, price, and platform.

**What it returns:**
A 2–4 sentence fit-card caption string ready to display in the UI. The caption should sound like a real user wrote it, not like a product description.

**What happens if it fails or returns nothing:**
If the outfit string is missing, empty, or only whitespace, the tool should return a clear error string instead of a caption. The agent should store that error in session state and stop rather than showing a broken fit card.

---

### Additional Tools (if any)

<!-- Copy the block above for any tools beyond the required three -->

---

## Planning Loop

**How does your agent decide which tool to call next?**
The planning loop runs in a fixed order and does not branch based on LLM reasoning. First it initializes the session, then it parses the query with simple regex and string cleanup to extract `description`, optional `size`, and optional `max_price`; if no price or size appears, those fields stay `None`.

Next it calls `search_listings(description, size, max_price)` and stores the list in `session["search_results"]`. If the list is empty, it sets `session["error"]` to a user-facing message such as "No listings matched that search. Try removing the size filter, widening the price range, or using broader keywords." and returns the session immediately.

If there are matches, it sets `session["selected_item"] = session["search_results"][0]` and calls `suggest_outfit(new_item=session["selected_item"], wardrobe=session["wardrobe"])`. If that call returns an empty string, it sets `session["error"]` to an outfit-generation failure message and returns early.

If outfit text is returned, it saves it to `session["outfit_suggestion"]`, then calls `create_fit_card(outfit=session["outfit_suggestion"], new_item=session["selected_item"])`. If the caption is empty or clearly invalid, it sets `session["error"]` and returns early. Otherwise it stores the caption in `session["fit_card"]` and returns the completed session.

---

## State Management

**How does information from one tool get passed to the next?**
The session dict is the single source of truth for one user interaction. It starts with `query`, `parsed`, `search_results`, `selected_item`, `wardrobe`, `outfit_suggestion`, `fit_card`, and `error`, and each tool writes one output field that the next step reads.

`parsed` stores the extracted search fields so the agent can reuse them without reparsing. `search_results` holds the full ranked list from the listing search, `selected_item` stores the first result, `outfit_suggestion` stores the outfit text returned by `suggest_outfit`, and `fit_card` stores the final caption returned by `create_fit_card`.

When any step fails, `error` is set and the function returns immediately. The UI should treat `error` as the stop signal and ignore later fields when it is not `None`.

---

## Error Handling

For each tool, describe the specific failure mode you're handling and what the agent does in response.

| Tool | Failure mode | Agent response |
|------|-------------|----------------|
| search_listings | No results match the query | Set `session["error"]` to a helpful message telling the user to broaden the search, remove the size filter, or raise the budget, then return immediately without calling later tools. |
| suggest_outfit | Wardrobe is empty | Still accept the call and return general styling advice for the selected item. If the tool output is blank for any reason, set `session["error"]` to a message saying styling advice could not be generated and stop. |
| create_fit_card | Outfit input is missing or incomplete | Return a descriptive error string or set `session["error"]` in the agent, then stop before showing a fit card. The user should only see the caption when the outfit text is valid. |

---

## Architecture

```mermaid
flowchart TD
     U[User query] --> P[Planning loop]
     P --> S[Parse query\n(description, size, max_price)]
     S --> L[search_listings(description, size, max_price)]
     L -->|results = []| E1[[Error: no listings found]]
     E1 --> R1[Return session with session.error]

     L -->|results[0..n]| C1[Session: search_results]
     C1 --> T[Select top result\nselected_item = results[0]]
     T --> O[suggest_outfit(new_item, wardrobe)]
     O -->|empty output| E2[[Error: no outfit suggestion]]
     E2 --> R2[Return session with session.error]

     O -->|outfit text| C2[Session: outfit_suggestion]
     C2 --> F[create_fit_card(outfit, new_item)]
     F -->|empty or invalid output| E3[[Error: invalid fit card]]
     E3 --> R3[Return session with session.error]

     F -->|caption| C3[Session: fit_card]
     C3 --> R4[Return completed session]

     P <--> ST[(Session state)]
     S <--> ST
     L <--> ST
     T <--> ST
     O <--> ST
     F <--> ST
```

---

## AI Tool Plan

<!-- For each part of the implementation below, describe:
     - Which AI tool you plan to use (Claude, Copilot, ChatGPT, etc.)
     - What you'll give it as input (which sections of this planning.md, your agent diagram)
     - What you expect it to produce
     - How you'll verify the output matches your spec before moving on

     "I'll use AI to help me code" is not a plan.
     "I'll give Claude my Tool 1 spec (inputs, return value, failure mode) and ask it to implement
     search_listings() using load_listings() from the data loader — then test it against 3 queries
     before trusting it" is a plan. -->

**Milestone 3 — Individual tool implementations:**

I will use Copilot for the three standalone functions in `tools.py`. For `search_listings`, I will give it the Tool 1 spec, the listing fields from `data/listings.json`, and the `load_listings()` helper from `utils/data_loader.py`; I expect code that filters by price and size, scores keyword overlap, and returns ranked listing dicts. I will verify it with at least one happy-path query, one broad query, and one no-results query.

For `suggest_outfit`, I will give Copilot the Tool 2 spec, the wardrobe schema from `data/wardrobe_schema.json`, and the requirement to use `new_item` plus wardrobe items in the prompt. I expect it to build a usable LLM prompt and handle empty wardrobes gracefully; I will verify that it returns non-empty styling text for both an example wardrobe and an empty wardrobe.

For `create_fit_card`, I will give Copilot the Tool 3 spec and the requirement to turn the outfit text into a 2–4 sentence caption. I expect it to validate the outfit input, call the model with the item details, and produce a casual caption that mentions the item name, price, and platform once each. I will verify the caption length and the presence of those three item details before wiring it into the agent.

**Milestone 4 — Planning loop and state management:**

I will use Copilot for `agent.py`, giving it the Planning Loop, State Management, Error Handling, and Architecture sections from this document. I expect it to implement the exact fixed-order flow: parse query, call `search_listings`, stop on no results, call `suggest_outfit`, stop on blank outfit text, call `create_fit_card`, and return the completed session.

Before trusting the implementation, I will run the CLI test in `agent.py` with a normal query, a no-results query, and an empty-wardrobe query. I will verify that the happy path fills `selected_item`, `outfit_suggestion`, and `fit_card`, that no-results returns early with `error`, and that the empty-wardrobe path still produces styling advice rather than crashing.

---

## A Complete Interaction (Step by Step)

Write out what a full user interaction looks like from start to finish — tool call by tool call. Use a specific example query.

**Example user query:** "I'm looking for a vintage graphic tee under $30. I mostly wear baggy jeans and chunky sneakers. What's out there and how would I style it?"

**Step 1:**
The agent parses the query into `description="vintage graphic tee"`, `size=None`, and `max_price=30.0`, then calls `search_listings(description="vintage graphic tee", size=None, max_price=30.0)`. `search_listings` returns a ranked list of matching listings, such as a black graphic tee or band tee under $30; if the list were empty, the agent would set an error message and stop here.

**Step 2:**
The agent stores the first result as `session["selected_item"]` and calls `suggest_outfit(new_item=session["selected_item"], wardrobe=session["wardrobe"])`. The tool returns outfit guidance such as pairing the tee with baggy jeans, chunky sneakers, and a small front tuck for shape.

**Step 3:**
The agent stores the outfit text in `session["outfit_suggestion"]` and calls `create_fit_card(outfit=session["outfit_suggestion"], new_item=session["selected_item"])`. The tool returns a short caption-like fit card that mentions the thrifted item, its price, and where it was found.

**Final output to user:**
The user sees the matched listing, the outfit suggestion, and the finished fit card. If step 1 finds nothing, the user sees a single error message with concrete search tips instead of any outfit or caption output.
