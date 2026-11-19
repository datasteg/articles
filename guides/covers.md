# Covers

The small picture next to an article in every list (Latest, a topic, a format): 160 × 107 px on a desktop, 80 × 54 px on a phone. It is the reader's first look at the article. It is a flat drawing in Glacier's colours, made by `make-cover` after the review passes, and approved by the editor together with the article at the publish gate.

Under the drawing the site adds a **plate** with what the article is built on: 11 indicators, 14 papers, 4 charts. You don't draw it (§ The plate).

## What a cover is for

- **Recognition.** A reader scanning the list can tell the article from its neighbours, and finds it again.
- **Subject, not decoration.** It shows what the article is about, in one picture: the thing it measures, or the mechanism its answer explains.
- **Trust.** Some readers are professionals. The cover looks like an economics publication's, not a stock-photo site's: calm, exact, understated.

The test: a member of the public understands it without a caption, and an economist finds nothing wrong in it.

## Choosing the idea

Start from the article's **answer** (`plan.json` `answer`, the English draft's title, dek, findings and insight), not from the question's keywords. Write three ideas, one line each, of three kinds:

| Kind | What it draws | Example |
|---|---|---|
| Object | The thing the article is about, drawn plainly | Two bond certificates side by side, one sitting a little lower; a container ship; a row of factory roofs |
| Mechanism | The relationship the answer explains, as a simple picture | A gap held open between two bars; a seesaw; two pipes with flows in opposite directions; a ladder with a missing rung |
| Data echo | The shape of the article's key chart, reduced to a motif: no axes, no labels, no values | A line that rose and then levelled; two lines with a band between them that widens, then narrows |

Score each idea on four things, then choose one:

1. **Fit**: does it say what the article says, and no more? If the answer is "no, this isn't a crisis", don't draw a crash. If it is "it depends", don't draw a verdict. A cover, like a chart headline, must not claim more than the article shows.
2. **Legibility at 80 × 54 px**: one focal shape that still reads when tiny.
3. **Distinctness**: different from the other covers on the site (`content/articles/*/cover.svg`, and `.preview/articles/*/cover.svg` for runs in flight). Not the same motif or composition twice in a row.
4. **Tone**: calm. Concern may show as tension (a gap, a tilt, a narrow ledge), never as alarm.

## What to draw, and what never to draw

Draw:
- flat shapes, few of them: 3–15 shapes, one focal element, set slightly off centre, with space around it;
- simple, generic objects that any reader recognises: a bond certificate, a coin seen edge-on, a ship, a crane, a factory, a column front for "a central bank" (generic, not a real building), a balance, a bridge, a ladder;
- a country cue only when the country is the subject, and only as a widely known silhouette drawn simply (a lighthouse, a tower); never a flag or a map outline.

Never draw:
- **text of any kind**: letters, numbers, currency signs (€ $ ₩), labels. The title sits next to the cover; text would be unreadable at 80 px and would need translating. The only numbers are the plate's, which the site writes;
- **people**: no faces or figures of real people (no central bankers), no caricatures;
- **logos, seals, banknotes or coins of real currencies, flags, maps with borders**: political, easy to get wrong, and they look like official material;
- **clichés**: bulls and bears, rockets, piggy banks, falling coins, rain of money, arrows smashing through floors, fire, explosions, storm clouds, red-and-green tickers, handshakes, globes with money;
- **a chart**: no axes, gridlines, ticks or values. A data echo is a motif; readers must not read it as data.

## Colour

Colours are class names, not values. Each maps to a Glacier token, so the cover follows the light and dark themes.
- Fill: `class="f-<name>"`.
- Stroke: `class="s-<name>"`.
- Both: `class="f-ice s-tarn"`.

| Name | Token | Use |
|---|---|---|
| `frost` | `surface-frost` | The default background (the list's thumbnail tile) |
| `ice` | `surface-ice` | A lighter background or large calm shapes |
| `paper` | `surface` | The page colour: cut-outs, highlights on dark shapes |
| `line` | `line` | Faint secondary shapes |
| `deep` | `deep` | A luminous ice panel |
| `strata` | `deep-strata` | Layer lines, secondary shapes on `deep` |
| `glint` | `deep-glint` | The one line that catches the light |
| `glacier` | `accent` | Bright cyan, the brand colour |
| `tarn` | `link` | Deep, readable blue |
| `crevasse` | `deep-accent` | The darkest blue in use (meltwater by night) |
| `focus` | `viz-focus` | The one thing the article is about |
| `context` | `viz-context` | Grey-blue for the things around it |
| `ink`, `ink2` | `ink`, `ink-secondary` | Outlines and small dark details |
| `seq1` … `seq7` | `seq-100` … `seq-700` | Light-to-dark blue steps for layers and depth |
| `warm` | `viz-2` | One warm accent, for the single thing that matters most. Use it on one shape at most |
| `lake`, `ochre` | `viz-3`, `viz-4` | A second object category, when two kinds of thing must be told apart |

Mostly blues and ice. No status colours: red and green mean good and bad on this site, and a cover is not a verdict. Check the dark render: a shape that stands out by day can vanish by night.

## Technical rules

`artools check cover --run <run>` enforces these; blocking problems stop the stage.

- **File:** `cover/cover.svg`, at most 12 KB, a root `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 480 320">` (3 : 2, the thumbnail's shape) with no `width` or `height`.
- **Elements:** only `g`, `rect`, `circle`, `ellipse`, `line`, `polyline`, `polygon` and `path`, at most 80 of them. No `text`, `image`, `use`, `defs`, gradients, filters, `style`, `script`, `foreignObject` or links.
- **Attributes:**
  - geometry;
  - `transform`, `class`;
  - `opacity`, `fill-opacity`, `stroke-opacity`;
  - `stroke-width`, `stroke-linecap`, `stroke-linejoin`, `stroke-dasharray`, `stroke-miterlimit`, `fill-rule`;
  - `fill="none"` and `stroke="none"`.

  No `id`, no `style` attribute, no colour values.
- **Every shape** has an `f-` class or `fill="none"`. SVG's default fill is black, which is not a Glacier colour.
- **Background:** the first element is the background, a rect over the full frame (`x="0" y="0" width="480" height="320"`).
- **Strokes:** at least 8 wide. That is 1.3 px on a phone; thinner lines vanish (below 4 is blocking).
- **Margins:** keep anything important 24 units inside the edges. The tile has rounded corners, and phones show it small.

## The plate

The site attaches a plate to the bottom of the tile, under the drawing. It doesn't cover the drawing. The plate holds three counts from the article's content, so a reader can check them:
- **indicators**: the data sources in the reference list, one per indicator. A yield for eleven countries counts once, as the reference list groups it;
- **papers**: the research publications cited (papers, policy notes, reports). Speeches don't count;
- **charts**: the charts drawn. The key-number tiles and tables don't count.

Beside a desktop card each count is a small stat, number over label, as in the article's key numbers. On a phone there is one count per line: "11 indicators", or label first in Korean, "지표 11". It uses the site's type, with a hairline above. A count of zero is left out. For economists the counts are part of the invitation: they say how much evidence stands behind the picture.

For the drawing, this means:
- the full 3 : 2 frame is still yours; the plate sits below it;
- the drawing's bottom edge meets the plate's hairline. A bottom band in `frost` runs into the plate's background; a ground line or a band in another tone ends the drawing cleanly;
- never repeat the counts, or any number, in the drawing.

## The record: `cover/cover.json`

```json
{
  "concept": {"en": "One sentence: what the picture shows and why it fits the answer", "ko": "…"},
  "alt": {"en": "What the picture shows, for screen readers and sharing (at most 125 characters)", "ko": "…"},
  "considered": [
    {"kind": "object", "idea": "…", "verdict": "…"},
    {"kind": "mechanism", "idea": "…", "verdict": "chosen: …"},
    {"kind": "data", "idea": "…", "verdict": "…"}
  ],
  "chosen": "mechanism",
  "rounds": 2,
  "checked": ["what each look at the renders changed"]
}
```

## Look before you finish

`artools render cover <run>` writes `cover/render/`. It shows the cover where readers meet it, through the real site:
- `card.<theme>.<width>.png`: the article's card in the Latest list, at 1040 and 375 px, light and dark;
- `tile.<theme>.png`: the thumbnail alone, enlarged;
- `list.light.1040.png`: the list with its neighbours.

Read every image and ask:
- Does the subject read at phone size?
- Do the drawing and the plate under it sit together as one tile?
- Does it work in both themes?
- Is it distinct from its neighbours?
- Is it calm, and true to the answer?

Fix and render again, three rounds at most.
