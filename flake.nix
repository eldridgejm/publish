{
  description = "Python package for streamlining end-of-quarter grading.";

  inputs.nixpkgs.url = github:NixOS/nixpkgs/20.03;

  outputs = { self, nixpkgs }: 
    let
      supportedSystems = [ "x86_64-linux" "x86_64-darwin" ];
      forAllSystems = f: nixpkgs.lib.genAttrs supportedSystems (system: f system);
    in
      {
        gradelib = forAllSystems (system:
          with import nixpkgs { system = "${system}"; };

            python3Packages.buildPythonPackage {
              name = "publish";
              src = ./.;
              propagatedBuildInputs = with python37Packages; [ pyyaml cerberus ];
              nativeBuildInputs = with python37Packages; [ pytest black ipython sphinx sphinx_rtd_theme ];
            }

          );

        defaultPackage = forAllSystems (system:
            self.gradelib.${system}
          );
      };

}
