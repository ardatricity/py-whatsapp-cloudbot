from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="python-whatsapp-cloudbot",
    version="0.1.2",
    author="Arda Koçak",
    author_email="ardatricity@gmail.com",
    description="An asynchronous Python library for the WhatsApp Cloud API.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/ardatricity/python-whatsapp-cloudbot",
    project_urls={
        "Bug Tracker": "https://github.com/ardatricity/python-whatsapp-cloudbot/issues",
        "Repository": "https://github.com/ardatricity/python-whatsapp-cloudbot",
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: GNU Lesser General Public License v3 or later (LGPLv3+)",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Communications :: Chat",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Typing :: Typed",
    ],
    packages=find_packages(include=['wa_cloud', 'wa_cloud.*']),
    include_package_data=True,
    license="LGPL-3.0-or-later",
    python_requires=">=3.8",
    install_requires=[
        "httpx >= 0.24.0",
        "pydantic >= 2.0.0",
    ],
    extras_require={
        "fastapi": [
            "fastapi >= 0.100.0",
            "uvicorn[standard] >= 0.20.0",
        ],
        "dev": [
            # "pytest",
            # "pytest-asyncio",
            # "ruff",
        ],
    },
)
