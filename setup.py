from setuptools import setup


setup(
    name="publish",
    version="0.1.4",
    py_modules=["publish"],
    install_requires=["pyyaml", "cerberus"],
    tests_require=["pytest"],
    entry_points={"console_scripts": ["publish = publish:cli"]},
)
