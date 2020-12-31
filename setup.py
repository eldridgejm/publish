from setuptools import setup, find_packages


setup(
    name="publish",
    version="0.1.5",
    packages=find_packages("publish"),
    install_requires=["pyyaml", "cerberus"],
    tests_require=["pytest"],
    entry_points={
        "console_scripts": [
            "publish = publish:cli",
            "publish-utils = publish.utils:cli",
        ]
    },
)
