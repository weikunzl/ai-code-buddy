#!/usr/bin/env python3
import pathlib
import subprocess
import tempfile
import textwrap
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
MAIN = ROOT / "src" / "main.cpp"
DATA = ROOT / "src" / "data.h"


class Utf8TextTests(unittest.TestCase):
    def test_utf8_helper_smoke(self):
        code = textwrap.dedent(
            r"""
            #include <cstring>
            #include <iostream>
            #include "utf8_text.h"

            static int expect_str(const char* got, const char* want, const char* label) {
              if (std::strcmp(got, want) != 0) {
                std::cerr << label << ": got=[" << got << "] want=[" << want << "]\n";
                return 1;
              }
              return 0;
            }

            int main() {
              char dst[8];
              utf8SafeCopy(dst, sizeof(dst), "你好世界");
              if (expect_str(dst, "你好", "utf8SafeCopy")) return 1;

              char line[32];
              const char* next = nullptr;
              utf8SliceColumns("alpha beta", line, sizeof(line), 6, &next, true, true);
              if (expect_str(line, "alpha", "utf8SliceColumns word")) return 1;
              utf8SliceColumns(next, line, sizeof(line), 6, &next, true, true);
              if (expect_str(line, "beta", "utf8SliceColumns next")) return 1;

              utf8SliceColumns("你好世界", line, sizeof(line), 4, &next, true, true);
              if (expect_str(line, "你好", "utf8SliceColumns cjk")) return 1;
              utf8SliceColumns(next, line, sizeof(line), 4, &next, true, true);
              if (expect_str(line, "世界", "utf8SliceColumns cjk next")) return 1;

              char rows[3][32] = {};
              uint8_t n = utf8WrapInto("你好世界", &rows[0][0], sizeof(rows[0]), 3, 5, true);
              if (n != 2) {
                std::cerr << "utf8WrapInto rows: got=" << (int)n << " want=2\n";
                return 1;
              }
              if (expect_str(rows[0], "你好", "utf8WrapInto row0")) return 1;
              if (expect_str(rows[1], " 世界", "utf8WrapInto row1")) return 1;

              if (utf8DisplayWidth("你好abc") != 7) {
                std::cerr << "utf8DisplayWidth failed\n";
                return 1;
              }
              return 0;
            }
            """
        )
        with tempfile.TemporaryDirectory() as tmp:
            src = pathlib.Path(tmp) / "utf8_smoke.cpp"
            exe = pathlib.Path(tmp) / "utf8_smoke"
            src.write_text(code)
            subprocess.run(
                ["c++", "-std=c++17", "-I", str(ROOT / "src"), str(src), "-o", str(exe)],
                check=True,
                capture_output=True,
                text=True,
            )
            subprocess.run([str(exe)], check=True, capture_output=True, text=True)

    def test_source_uses_utf8_helpers(self):
        main = MAIN.read_text()
        data = DATA.read_text()
        self.assertIn('#include "utf8_text.h"', data)
        self.assertIn("utf8SafeCopy(dst, n, src);", data)
        self.assertIn("enum UiScript", main)
        self.assertIn("detectUiScript(", main)
        self.assertIn("mergeUiScript(", main)
        self.assertIn("struct UiCompactLayout", main)
        self.assertIn("uiCompactLayoutFor(", main)
        self.assertIn("uiBodyFontFor(", main)
        self.assertIn("uiTitleFontFor(", main)
        self.assertIn("&fonts::efontCN_10", main)
        self.assertIn("&fonts::efontJA_10", main)
        self.assertIn("&fonts::efontKR_10", main)
        self.assertIn("&fonts::efontCN_12", main)
        self.assertIn("&fonts::efontJA_12", main)
        self.assertIn("&fonts::efontKR_12", main)
        self.assertIn("setUiBodyFont(", main)
        self.assertIn("setUiTitleFont(", main)
        self.assertIn("utf8LineSlice(", main)
        self.assertIn("utf8DisplayWidth(", main)
        self.assertIn("utf8WrapInto(", main)
        for legacy in ("%.21s", "%.17s", "%.16s", "%.12s", "+ 21", "+ 17"):
            self.assertNotIn(legacy, main)


if __name__ == "__main__":
    unittest.main()
