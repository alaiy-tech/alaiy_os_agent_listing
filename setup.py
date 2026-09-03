from setuptools import setup, find_packages

with open("requirements.txt") as f:
    # Keep only real requirement lines; skip blanks and "#" comments so that
    # documentation comments in requirements.txt are not treated as packages.
    install_requires = [
        line.strip()
        for line in f
        if line.strip() and not line.strip().startswith("#")
    ]

from alaiy_os_agent_listing import __version__ as version

setup(
    name="alaiy_os_agent_listing",
    version=version,
    description="The listing agent for Alaiy OS — one agent, whichever sales channels the site has.",
    author="Alaiy",
    author_email="mail@alaiy.com",
    packages=find_packages(),
    zip_safe=False,
    include_package_data=True,
    install_requires=install_requires,
)
