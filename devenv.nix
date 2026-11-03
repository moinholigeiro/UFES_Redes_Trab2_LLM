{ pkgs, ... }:
{
  packages = [
    pkgs.llama-cpp
    pkgs.curl
    pkgs.jq
    pkgs.python313
    pkgs.openssl
  ];
  env.PYTHONUNBUFFERED = "1";
  enterShell = ''
    echo "llama-server: $(llama-server --version 2>/dev/null | head -1)" >&2
    echo "Python: $(python --version)" >&2
  '';
}
