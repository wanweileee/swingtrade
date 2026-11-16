# swing-agents

A small, readable multi-agent flow for weekend swing trading, modelled on
[TradingAgents](https://github.com/TauricResearch/TradingAgents) (Apache-2.0) but
rebuilt around **your** strategy, risk rules and playbook. No social/sentiment
agents. Every step saves what it read, what it wrote and every AI prompt, so you
can open the run and see exactly how a decision was reached.

**Rules decide, AI assists.** The strategy file and `risk.py` are plain code. The
AI analysts can argue and can turn a trade down (WAIT / SKIP / VETO), but they
can never create a trade the rules didn't produce, or make it bigger.

Educational/paper-trading tool, not investment advice.

---

## The flow

```
setup → 01 fetch_data → 02 market_regime → 03 strategy_rules
                                              │
              no signal / market RED ─────────┼──────────────────────────┐
                                              ▼                          │
   04 technical → 05 fundamentals → 06 news → 07 bull ⇄ 08 bear          │
                                              ▼                          │
                         09 research_manager (TAKE / WAIT / SKIP)        │
                                              ▼                          │
                  10 trade_plan (code) → 11 risk_check (code + AI veto)  │
                                              ▼                          │
                                    12 final_decision  ◄─────────────────┘
                                    BUY  /  WATCH  /  SKIP
```

| Step | Type | What it does | File |
|---|---|---|---|
| fetch_data | code | Daily prices for ticker + SPY, fundamentals, next earnings, headlines | `nodes/data_nodes.py`, `data.py` |
| market_regime | code | SPY above its 200-day SMA? | `nodes/data_nodes.py` |
| strategy_rules | code | Runs your strategy file; every rule passed/failed with numbers | `strategies/*.py` |
| technical / fundamentals / news | AI | Short reports judged against *your* strategy and playbook | `nodes/analysts.py`, `prompts/*.md` |
| bull ⇄ bear | AI | Debate for/against this week's trade (rounds in config) | `nodes/debate.py` |
| research_manager | AI | Judges the debate → TAKE / WAIT / SKIP | `nodes/debate.py` |
| trade_plan | code | Entry, stop, shares from risk % and stop distance, 1R/2R | `nodes/decision.py`, `risk.py` |
| risk_check | code + AI | Hard rules (slots, sector, earnings, drawdown), then AI may veto | `risk.py`, `nodes/decision.py` |
| final_decision | code | Combines every gate; writes `report.md` with an order ticket | `nodes/decision.py` |

---

## Phone app (no laptop needed)

GitHub runs the flow every **Saturday 12:36 SGT** and publishes the results to a
small web app you add to your phone's home screen ("Swing Desk"). It shows the
market filter, a card per ticker (BUY / WATCH / SKIP), the order ticket, the rule
checks and every step of the flow with its output, input and AI prompt/answer.
It works offline with the last results.

### One-time setup (about 15 min, phone or laptop)

1. **Create a repo.** On github.com → New repository → name it `swing-agents`,
   Public → Create. Upload this whole folder (drag the unzipped files into
   "uploading an existing file", including the hidden `.github` folder, or use
   `git push` from a laptop once).
2. **Add your API key.** Repo → Settings → Secrets and variables → Actions →
   New repository secret → name `ANTHROPIC_API_KEY`, paste your key.
   (Get one at console.anthropic.com. Using OpenAI instead? Add `OPENAI_API_KEY`
   and change the models in `config.yaml`.)
3. **Turn on the site.** Settings → Pages → Source: *Deploy from a branch* →
   Branch `main`, folder `/docs` → Save. Your app URL appears there, like
   `https://<your-username>.github.io/swing-agents/`.
4. **Test it.** Actions tab → "Weekly swing run" → Run workflow → tick
   *Offline test* → Run. After ~2 min, open the app URL. Then run once without
   *Offline* to see real AI analysis.
5. **Add to home screen.** iPhone: open the URL in Safari → Share → *Add to Home
   Screen*. Android: Chrome → ⋮ → *Add to Home screen*.

### Everyday use
- **Saturday:** the run happens on its own. Open Swing Desk, tap the BUY/WATCH
  names, check the chart in TradingView, place paper orders.
- **Run now / other tickers:** GitHub app → repo → Actions → "Weekly swing run"
  → Run workflow → type tickers (e.g. `MSFT XOM`).
- **Update positions, watchlist, playbook:** edit `portfolio.yaml`,
  `watchlist.txt` or `knowledge/*.md` directly on github.com (pencil icon). The
  next run uses them.
- The page is public: anyone with the link can see the analysis (no account or
  money data is in it). GitHub's scheduled runs can start a few minutes late.

---

## Setup on a laptop (optional, for coding)

```bash
cd swing-agents
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env               # put your ANTHROPIC_API_KEY (or OPENAI_API_KEY) in .env
```

## Use it

```bash
python run.py MSFT XOM --offline        # test the plumbing, no API key, no cost
python run.py MSFT XOM                  # real AI analysis (last trading day)
python run.py MSFT --date 2026-11-13    # a specific Friday
python run.py --watchlist               # everything in watchlist.txt
python run.py MSFT --strategy breakout_20d

streamlit run viewer.py                 # open the step-by-step viewer
```

Each step prints as it finishes. Everything is saved to
`runs/<time>/<TICKER>/` — one JSON per step, `index.json`, and `report.md`.

**Weekend routine:** Saturday after 5am SGT, run `python run.py --watchlist`,
open the viewer, read the BUY/WATCH names, confirm each on your TradingView chart
with your Pine script, then place the paper orders.

**Cost:** with Haiku for analysts and Sonnet for the judge/reviewer, one ticker
that reaches the AI steps is roughly 7–9 calls. Tickers with no signal skip the AI
entirely (`skip_llm_if_no_signal: true`), so a 10-stock watchlist usually costs cents.

---

## Where to change what

| I want to… | Change |
|---|---|
| Swap strategy | `config.yaml → strategy: breakout_20d` (or `--strategy`) |
| Tweak a parameter (e.g. RSI 45) | `config.yaml → strategy_params` |
| Write my own strategy | Copy `strategies/pullback_v2.py` → `strategies/my_idea.py`, edit `PARAMS`, `DESCRIPTION`, `prepare`, `evaluate`. Set `strategy: my_idea`. |
| Change what an agent focuses on | Edit its prompt in `swing_agents/prompts/<agent>.md` (plain text, `{placeholders}` are filled in) |
| Teach the agents my rules/lessons | Edit `knowledge/playbook.md`, add lines to `knowledge/lessons.md` after each trade |
| Change account, risk %, max positions, earnings blackout | `config.yaml → account` |
| Record open positions (for slot/sector limits) | `portfolio.yaml` |
| Turn an analyst off | `config.yaml → flow.analysts` |
| More debate | `config.yaml → flow.debate_rounds` |
| Use OpenAI / a local model | `config.yaml → llm.quick_model: openai:gpt-4o-mini` or `ollama:llama3.1` (install `langchain-ollama`) |
| Use TradingView data instead of Yahoo | Export chart data to `data/csv/<TICKER>.csv` (and SPY), set `data.source: csv` |
| Add a new step | Write a function in `swing_agents/nodes/`, decorate it with `@step("name", "Title", reads=[...])`, add the node and edges in `swing_agents/graph.py`, add its keys to `state.py` |
| Change the BUY/WATCH/SKIP logic | `final_decision` in `swing_agents/nodes/decision.py` |
| Add an indicator | `swing_agents/indicators.py` |
| Change the phone app's look or layout | `docs/index.html` (one file, plain HTML/CSS/JS) |
| Change the Saturday time | cron line in `.github/workflows/weekly.yml` (UTC; `36 4 * * 6` = Sat 12:36 SGT) |

### Anatomy of a step

```python
@step("news_analyst", "News analyst (AI)", reads=["news"])   # recorded automatically
def news_analyst(state: dict) -> dict:
    prompt = render("news_analyst", "the News Analyst", state, news=...)  # prompts/news_analyst.md
    return {"reports": {..., "news": ask(state["config"], prompt)}}       # new state keys
```

A step takes the shared state and returns only the keys it adds. The `@step`
decorator saves `reads`, the returned dict, timings and every `ask()` call.

### Strategy contract

```python
class MyIdea(Strategy):
    NAME = "My idea"
    PARAMS = {"rsi_max": 45, ...}            # defaults; config can override
    DESCRIPTION = """rules in words..."""    # the AI agents read this
    def prepare(self, df):  ...              # add indicator columns
    def evaluate(self, df): ...              # → SignalResult(signal, checks, entry, stop)
STRATEGY = MyIdea
```

---

## Visual graph (optional)

`langgraph.json` is included, so LangGraph Studio can draw and step through the
graph: `pip install "langgraph-cli[inmem]"` then `langgraph dev`, and run it with
input `{"ticker": "MSFT"}`. The Streamlit viewer works without it.

## Folder map

```
config.yaml            all settings
portfolio.yaml         your open positions
watchlist.txt          tickers for --watchlist
knowledge/             playbook + lessons every agent reads
strategies/            one file per strategy (pullback_v2, breakout_20d)
swing_agents/
  graph.py             the flow wiring
  state.py             every key in the shared state
  nodes/               the steps
  prompts/             one .md prompt per agent (+ _header.md shared)
  risk.py              sizing + hard rules
  llm.py               model calls (+ offline stub)
  recorder.py          saves each step to runs/
  data.py, indicators.py
run.py                 terminal runner
viewer.py              Streamlit step viewer (laptop)
export_web.py          runs/ → docs/data for the phone app
docs/                  the phone app (index.html, manifest, service worker, icons)
.github/workflows/     the Saturday GitHub run
```

## Notes and limits

- Indicators match TradingView's EMA/RSI/ATR formulas, but Yahoo and TradingView
  data can differ slightly. Your Pine script on TradingView is the final check.
- Yahoo's earnings dates are sometimes missing; the risk step then fails
  "Earnings clear" on purpose, so you check manually.
- AI backtests are unreliable (models may have seen past prices in training).
  Judge the AI layer by forward paper-trading: compare BUYs the AI approved vs
  ones it vetoed over 30+ setups.
