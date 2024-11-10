from setuptools import setup, find_packages

setup(
    name="journ_app",
    version="1.0.3",
    author="Austin Wiggins",
    author_email="Austinlamarwiggins@gmail.com",
    url="https://github.com/AlamarW/journ",
    packages=find_packages(),
    description="A CLI Journaling that honors your text editor of choice",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    entry_points={
        "console_scripts": [
            "journ=journ.main:main",
        ]
    },
    python_requires=">=3.6",
)
