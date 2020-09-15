from setuptools import setup


setup(
    name="publish",
    version="0.1.0",
    py_modules=["publish"],
    install_requires=["pyyaml", "yamale"],
    tests_require=["pytest", "black"],
    entry_points={"console_scripts": ["publish = publish:cli"]},
)
