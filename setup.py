from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as f:
    long_description = f.read()

setup(
    name="seraph",
    version="1.0.0",
    author="Mohammed",
    description="Python's guardian angel — fixes the 5 most painful Python developer experiences.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourname/seraph",
    packages=find_packages(),
    python_requires=">=3.8",
    extras_require={
        "timezones": ["pytz"],   # only needed on Python 3.8 for named TZ support
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Utilities",
    ],
    keywords="utilities threading datetime pathlib optional chaining watchdog",
)
