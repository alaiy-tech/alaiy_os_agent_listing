app_name = "alaiy_os_agent_listing"
app_title = "Alaiy Os Agent Listing"
app_publisher = "Alaiy"
app_description = "The listing agent for AlaiyOS — one agent, whichever sales channels the site has"
app_email = "mail@alaiy.com"
app_license = "agpl-3.0"

# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------
# The agent engine, OS Agent Registry and OS Agent Run all live in alaiy_os.
#
# No channel connector is required, and none is named anywhere in this app. A
# channel arrives through the `listing_channels` hook when its connector is
# installed (see channels.py), so this app installs and registers its agent on a
# bench with no sales channel at all — the agent simply says there is nothing to
# write a listing for until one shows up. That is what makes it shippable by
# default rather than something a deployment has to opt into.
required_apps = ["alaiy_os"]

# ---------------------------------------------------------------------------
# Installation / migration
# ---------------------------------------------------------------------------
# sync_agent_registry() (re)registers the listing agent in alaiy_os's OS Agent
# Registry, with any customer override (<app>/agents/listing.md) appended to its
# prompt. It is idempotent, so it runs on both install (the agent works
# immediately) and every migrate (edits to the prompt or the override reconcile
# onto the site).
after_install = [
    "alaiy_os_agent_listing.setup.install.sync_agent_registry",
]

after_migrate = [
    "alaiy_os_agent_listing.setup.install.sync_agent_registry",
]

# ---------------------------------------------------------------------------
# Uninstallation
# ---------------------------------------------------------------------------
# Remove the agent's OS Agent Registry row. OS Agent Run history is kept.
before_uninstall = [
    "alaiy_os_agent_listing.setup.install.unregister",
]
