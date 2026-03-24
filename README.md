# Consensus

Ask a question. Watch language models independently research it, argue about it, and vote.

![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)
![Python](https://img.shields.io/badge/python-3.10+-blue.svg)
![Flask](https://img.shields.io/badge/flask-3.0+-lightgrey.svg)
[![Live](https://img.shields.io/badge/live-dr.eamer.dev%2Fconsensus-blue.svg)](https://dr.eamer.dev/consensus/)

## What it does

You type a question. 8+ language models from different providers each independently research it and form an opinion. They vote — AGREE, DISAGREE, or PARTIAL — and you see the whole debate play out in a live tree visualization.

Not all votes are equal. Anthropic and Gemini carry more weight (they're royalty). OpenAI and xAI are lords. Mistral, Cohere, Groq, and Perplexity are knights. Each provider can run multiple sub-models, so you see the family tree branch out — Anthropic splits into Sonnet and Haiku, Gemini into Flash and Pro, and so on.

The tree lights up as each model starts thinking. Votes cascade from sub-models up to providers, then to the final consensus. Green for agree, red for disagree, amber for split.

## The hierarchy

| Rank | Provider | Weight | Models |
|------|----------|--------|--------|
| Queen | Anthropic | 3× | Sonnet 4.5, Haiku 4.5 |
| King | Gemini | 3× | Flash 2.5, Flash 2.0 |
| Lord | OpenAI | 2× | GPT-4o, GPT-4o Mini |
| Lord | xAI | 2× | Grok 3 Mini |
| Knight | Mistral | 1× | Mistral Small |
| Knight | Cohere | 1× | Command R+ |
| Knight | Groq | 1× | Llama 3.3 70B, DeepSeek R1 |
| Knight | Perplexity | 1× | Sonar |

Toggle providers on and off before each debate. The tree adapts.

## Quick start

```bash
git clone https://github.com/lukeslp/consensus.git
cd consensus
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
```

Set at least one API key — you don't need all of them, just the providers you want to include:

```bash
export ANTHROPIC_API_KEY=...
export GEMINI_API_KEY=...
export OPENAI_API_KEY=...
export XAI_API_KEY=...
export MISTRAL_API_KEY=...
export COHERE_API_KEY=...
export GROQ_API_KEY=...
export PERPLEXITY_API_KEY=...
```

```bash
python app.py
# http://localhost:5063
```

Press `Cmd+Enter` (or `Ctrl+Enter`) to start a debate.

> **Note:** This project uses a shared LLM provider library (`llm_providers`) for unified auth, rate limiting, and streaming across providers. That library is bundled as part of the broader geepers ecosystem and is not yet published as a standalone package. If you're running into import errors, the library needs to be on your Python path — raise an issue and we can work out the best way to package it.

## Architecture

```
Browser → Flask (port 5063) → LLM providers (parallel threads)
                ↓
         SSE event stream → D3.js tree visualization
```

One Flask file, one HTML file. The backend fires all providers in parallel threads, streams events over SSE as each model responds. The frontend renders a D3.js tree that updates in real time.

## How voting works

Each model gets the same system prompt: research the question, state your confidence, and cast a vote (AGREE / DISAGREE / PARTIAL) with a one-sentence summary. Sub-model votes roll up to a provider-level stance, then a weighted final consensus.

The weight system means Anthropic and Gemini together can overrule all the knights — but if every knight disagrees, the split shows up clearly in the visualization.

## License

MIT

---

**Luke Steuber** · [lukesteuber.com](https://lukesteuber.com) · [@lukesteuber.com](https://bsky.app/profile/lukesteuber.com)
