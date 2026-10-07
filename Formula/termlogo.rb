class Termlogo < Formula
  desc "Logo interpreter with turtle graphics for the terminal"
  homepage "https://github.com/andybateman/termlogo"
  url "https://github.com/andybateman/termlogo/archive/refs/tags/v1.2.0.tar.gz"
  sha256 "59e872cbb72af384107910621a150ac03f0a0aa7ea175ad2881a75cfedbeeb44"
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
    assert_match "termlogo 1.2.0", shell_output("#{bin}/termlogo --version")
  end
end
