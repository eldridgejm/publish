from setuptools import setup, find_packages


setup(
    name="publish",
    version="0.2.1",
    packages=find_packages(),
    install_requires=["pyyaml", "cerberus", "jinja2"],
    tests_require=["pytest"],
    entry_points={
        "console_scripts": [
            "publish = publish:cli",
            "publish-utils = publish.utils:cli",
        ]
    },
)
