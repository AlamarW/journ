from setuptools import setup, find_packages

setup(
        name="journ",
        version="1.0.0",
        packages=find_packages(),
        install_requires=[],
        entry_points={
            "console_scripts": [
                "journ=journ.main:main",
            ]
        },
        author="Austin Wiggins",
        author_email="austinlamarwiggins@gmail.com",
        description="A CLI Journaling tool",
        long_description=open("README.md").read(),
        long_description_content_type="text/markdown",
        url="https://github.com/AlamarW/journ",
        classifiers=[
            "Programming Langauges :: Python :: 3",
            "License :: OSI Approved :: MIT License",
            "Operating System :: OS Independent",
        ],
        python_requires=">=3.6",
)

