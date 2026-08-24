{
  description = "Development environment for watermark_tool";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  };

  outputs = { self, nixpkgs }:
    let
      system = "x86_64-linux";
      pkgs = nixpkgs.legacyPackages.${system};
      
      runtimeLibs = with pkgs; [
        stdenv.cc.cc.lib
        zlib
        glib
        libGL
        ffmpeg
      ];
    in
    {
      devShells.${system}.default = pkgs.mkShell {
        buildInputs = with pkgs; [
          python312
          python312Packages.pip
          python312Packages.virtualenv
          ffmpeg
        ] ++ runtimeLibs;

        shellHook = ''
          export LD_LIBRARY_PATH="${pkgs.lib.makeLibraryPath runtimeLibs}:$LD_LIBRARY_PATH"
          if [ -d ".venv" ]; then
            source .venv/bin/activate
          fi
        '';
      };
    };
}
