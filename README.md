# alaiy_os_agent_listing

The listing agent for Alaiy OS. **One agent, whichever sales channels the site has.**

Given a product identifier, it writes that product's channel listing — title,
description, images, and whatever else the channel asks for — and lands it in
review for an admin to approve. It never publishes. Where the channel reports
problems with a listing that is already live, it also says what is wrong and
fixes what it can.

```
/listing ABC-123          in Ask Alaiy
run_agent("listing", {"product": "ABC-123"})    everywhere else
```

## It does not know what a marketplace is

This app contains no reference to Amazon, Shopify, or any other channel, and that
is the whole design. What a channel wants from a listing is a fact about that
channel, so it comes from the app that owns the channel — its connector — through
a list hook:

```python
# in a connector's hooks.py
listing_channels = ["alaiy_os_connector_amazon_sp_api.listing_channel.channel"]
```

Each entry returns an adapter: the channel's own fields and rules, a validator,
and handlers for reading a product, preparing its images and saving the result.
`channels.py` documents the full contract.

Adding a channel is one adapter in one connector. Nothing in this app, and
nothing in core, changes.

### The channel's fields are a tool result, not a schema

The one thing worth understanding before changing anything here.

An `OS Agent Registry` row holds a single `output_schema`, and two channels on
the same bench typically share only a handful of fields. There were two ways to
live with that and both are worse than what this app does:

- **Merge them into a superset.** Every channel's own fields become optional, and
  a field the schema says is optional is a field the model treats as optional.
  This is exactly how the rules that matter — a title's length, an exact bullet
  count, a byte budget on search terms — get quietly dropped.
- **One row per channel.** Buys strictness back at the price of the second agent
  this app exists to remove, plus a dispatch seam in `chat/skills.py`, because
  `skill_slug` is unique per row.

So the schema on the row is the floor every channel shares, and the channel's own
requirements are handed to the model at runtime by `get_channel_spec` as an
ordinary tool result. One extra round trip, and both properties are kept.

Strictness then lives in the adapter's `validate`, which is Python and can say
what JSON Schema cannot: a total byte budget, a banned-term list, "no keyword
that already appears in the title". `save_listing` runs it before writing
anything and refuses in words the model reads and acts on — the same correction
loop a denied permission already takes.

## Layout

```
agent_meta.py        the manifest: prompt, shared schema, tools, the /listing skill
channels.py          the listing_channels contract, and channel resolution
tools/handlers.py    the tools — all channel-agnostic, all dispatching
prompts/system.md    the craft that is true of every channel
schemas/output.json  the fields every channel must produce
setup/install.py     upserts the one OS Agent Registry row
```

## Customising it for a seller

Drop a markdown file at `<customer_app>/agents/listing.md`. It is appended to the
prompt, and it is for facts about the **seller** — house brands, tone, what they
sell. Anything true of a *channel* belongs in that channel's adapter instead,
where every site running it benefits.

Optional frontmatter sets `model` and `description`.

## Running one without the UI

```bash
bench --site <site> execute alaiy_os.api.agents.run_agent \
  --kwargs "{'agent':'listing','payload':{'product':'<sku>'}}"
```

`channel` is optional: with one omitted, the identifier is looked up across every
registered channel and resolves when exactly one has it. A product listed on two
channels asks which, rather than picking.
