# alaiy_os_agents

**The default agents Alaiy OS ships.** One app, several agents, each one enabled
or disabled per site.

The code is on every bench that has this app. Nothing runs until someone turns an
agent on in **Settings → Agents** — and turning it on is exactly what makes Ask
Alaiy able to use it.

## Ships installed, starts disabled

Each agent is registered into `OS Agent Registry` with `is_enabled = 0` on first
insert. That flag is the only switch, because it is the one the rest of Alaiy OS
already reads:

| Reader | What `is_enabled` decides |
|---|---|
| `chat/skills.py` | whether the agent appears in the `/` catalogue |
| `chat/agents.py` | whether `run_agent` will hand it work from plain language |
| `chat/tools.py` | whether its tools reach the chat's tool surface at all |

So enabling an agent is a complete on switch and disabling it a complete off one.
There is no second place to wire, and nothing here to keep in step with the chat.

Off by default because agents are not free: an agent is a model, its tools, and
whatever they touch — spend, and in some cases writes. A bench should not acquire
any of that by upgrading an app.

After the first insert `is_enabled` belongs to the operator. A migrate never
re-disables an agent someone turned on, nor re-enables one they turned off.

## Adding an agent

Make a directory under `agents/` with a `meta.py` exposing `build_agent_meta()`.
That is the entire contract — `registry.py` walks `agents/`, imports each
subpackage, and upserts whatever declares itself. Nothing else has to learn the
new agent's name: the directory *is* the list.

```
agents/
  listing/
    meta.py       build_agent_meta() -> the manifest
    channels.py   its own seams
    tools.py      its handlers
    prompts/      its prompt
    schemas/      its output schema
```

A directory without `build_agent_meta` is skipped rather than treated as broken,
so shared helpers can live there too.

The manifest names its own writers under `writes`; `registry.py` marks those
tools `effect: write`, which keeps them off Ask Alaiy's directly-callable surface
so anything that changes state is only reached inside a run that applied the
agent's own rules.

## The agents

### `listing`

Writes a channel-ready product listing, for whichever sales channel the product
is on, and diagnoses why a live listing was rejected or suppressed. Lands in
review; it never publishes.

It contains no reference to Amazon, Shopify or any other channel. What a channel
wants from a listing is a fact about that channel, so it arrives from the app
that owns the channel — its connector — through a list hook:

```python
# in a connector's hooks.py
listing_channels = ["alaiy_os_connector_amazon_sp_api.listing.channel.channel"]
```

`agents/listing/channels.py` documents the adapter contract. Adding a channel is
one adapter in one connector; nothing in this app changes.

**The channel's fields are a tool result, not a schema** — the one thing to
understand before changing anything here. A registry row holds a single
`output_schema`, and two channels typically share only a handful of fields.
Merging them into a superset makes every channel's own fields optional, which is
how rules like an exact bullet count or a byte budget get quietly dropped; a row
per channel buys strictness back at the price of a second agent. So the schema is
the floor every channel shares, and the rest is handed over at runtime by
`get_channel_spec`. Strictness lives in the adapter's `validate`, which is Python
and can say what JSON Schema cannot.

## Running one without the UI

```bash
bench --site <site> execute alaiy_os.api.agents.run_agent \
  --kwargs "{'agent':'listing','payload':{'product':'<sku>'}}"
```

A disabled agent refuses here too — `is_enabled` is checked before the run, not
just in the chat.
