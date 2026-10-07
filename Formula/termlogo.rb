class Termlogo < Formula
  desc "Logo interpreter with turtle graphics for the terminal"
  homepage "https://github.com/andybateman/termlogo"
  url "https://github.com/andybateman/termlogo/archive/refs/tags/v1.1.0.tar.gz"
  sha256 "2c2388a97774a76f4ef4fa4f1de462713dc8a0dcc33e788ba81c1b13a4b17148"
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
    assert_match "termlogo 1.1.0", shell_output("#{bin}/termlogo --version")
  end
end
