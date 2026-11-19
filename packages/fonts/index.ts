// Glacier fonts, self-hosted from npm (all SIL OFL 1.1). Every face ships as unicode-range slices,
// so a page downloads only the glyphs it uses: English pages fetch no Hangul serif files.
// font-display: swap is set by each package. Import this module once, in the root layout.
import '@fontsource-variable/hanken-grotesk/index.css'; // "Hanken Grotesk Variable"
import '@fontsource-variable/source-serif-4/opsz.css'; // "Source Serif 4 Variable", optical sizes
import '@fontsource-variable/source-serif-4/opsz-italic.css';
import '@fontsource-variable/jetbrains-mono/index.css'; // "JetBrains Mono Variable"
import '@fontsource/noto-serif-kr/400.css'; // "Noto Serif KR"
import '@fontsource/noto-serif-kr/600.css';
import '@fontsource/noto-serif-kr/700.css';
import 'pretendard/dist/web/variable/pretendardvariable-dynamic-subset.css'; // "Pretendard Variable"
import './fonts.css';
