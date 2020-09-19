with import <nixpkgs> {};

python37Packages.buildPythonPackage {
  name = "publish";
  src = ./.;
  propagatedBuildInputs = with python37Packages; [ pyyaml cerberus ];
  nativeBuildInputs = with python37Packages; [ pytest black ipython sphinx sphinx_rtd_theme ];
}
