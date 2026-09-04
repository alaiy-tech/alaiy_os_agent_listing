app_name = "alaiy_os_agents"
app_title = "Alaiy OS Agents"
app_publisher = "Alaiy"
app_description = "The default agents Alaiy OS ships — installed everywhere, each enabled per site"
app_email = "mail@alaiy.com"
app_license = "agpl-3.0"

# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------
# The agent engine, OS Agent Registry and OS Agent Run all live in alaiy_os.
#
# Nothing else, and no connector. An agent here reaches whatever a site happens to
# have through a seam of its own — the listing agent takes its channels from the
# `listing_channels` hook — so this app installs on a bench with no sales channel,
# no supplier and no marketplace credentials at all. That is what makes it
# shippable by default rather than something a deployment opts into.
required_apps = ["alaiy_os"]

# ---------------------------------------------------------------------------
# Installation / migration
# ---------------------------------------------------------------------------
# registry.sync() walks agents/ and upserts every agent it finds, on install and
# on every migrate, so editing a prompt and migrating reconciles it onto the site.
#
# Each agent lands **disabled**. The code ships with the app; whether a site runs
# any given agent is a decision made in the Agents settings screen, and it is
# `is_enabled` that Ask Alaiy reads — see registry.py.
after_install = ["alaiy_os_agents.registry.sync"]
after_migrate = ["alaiy_os_agents.registry.sync"]

# ---------------------------------------------------------------------------
# Uninstallation
# ---------------------------------------------------------------------------
# Remove every agent's registry row. OS Agent Run history is kept.
before_uninstall = ["alaiy_os_agents.registry.unregister"]
