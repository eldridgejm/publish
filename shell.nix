with import <nixpkgs> {};

let
  yamale = python37Packages.buildPythonPackage {
    name = "yamale";
    src = fetchFromGitHub {
      owner = "23andMe";
      repo = "yamale";
      rev = "c535f3afec18b97713b068b1f1ca47324983c596";
      sha256 = "1xjvah4r3gpwk4zxql3c9jpllb34k175fm6iq1zvsd2vv2fwf8s2";
    };
    propagatedBuildInputs = with python37Packages; [ pyyaml ];
    buildInputs = with python37Packages; [ tox pytest ];
  };
in
  python37Packages.buildPythonPackage {
    name = "publish";
    src = ./.;
    propagatedBuildInputs = with python37Packages; [ pyyaml yamale ];
    nativeBuildInputs = with python37Packages; [ pytest black ipython ];
  }
