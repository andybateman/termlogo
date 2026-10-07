class Termlogo < Formula
  desc "Logo interpreter with turtle graphics for the terminal"
  homepage "https://github.com/andybateman/termlogo"
  url "https://github.com/andybateman/termlogo/archive/refs/tags/v1.0.0.tar.gz"
  sha256 "0f86af4e54ea6fb6f5ee5c214b039f5f0d1bd964c920d6f67d9e0bac64f3ac30"
  license "MIT"

  depends_on "python@3.13"

  def install
    libexec.install "termlogo"
    (bin/"termlogo").write <<~SH
      #!/bin/sh
      PYTHONPATH="#{libexec}" exec "#{Formula["python@3.13"].opt_bin}/python3.13" -m termlogo "$@"
    SH
  end

  test do
    assert_match "termlogo 1.0.0", shell_output("#{bin}/termlogo --version")
  end
end
