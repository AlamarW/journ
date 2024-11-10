from setuptools import setup, find_packages

setup(
    name="journ",
    version="0.1.0",
    packages=find_packages(),
    entry_points={
        "console_scripts": [
            "journ=journ.main:main",
        ]
    },
    python_requires=">=3.6",
)
