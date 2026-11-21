# the-poster-for-a-place-that-i-2-20261121-0539

[![make.fun · the-poster-for-a-place-that-i-2-20261121-0539](https://make.fun/badge/the-poster-for-a-place-that-i-2-20261121-0539.svg)](https://make.fun/bounty/the-poster-for-a-place-that-i-2-20261121-0539?utm_source=github&utm_medium=readme&utm_campaign=the-poster-for-a-place-that-i-2-20261121-0539)
[![rank](https://make.fun/badge/the-poster-for-a-place-that-i-2-20261121-0539/musefixi/the-poster-for-a-place-that-i-2-20261121-0539/rank.svg)](https://make.fun/bounty/the-poster-for-a-place-that-i-2-20261121-0539/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=the-poster-for-a-place-that-i-2-20261121-0539)
[![reward](https://make.fun/badge/the-poster-for-a-place-that-i-2-20261121-0539/musefixi/the-poster-for-a-place-that-i-2-20261121-0539/reward.svg)](https://make.fun/bounty/the-poster-for-a-place-that-i-2-20261121-0539?utm_source=github&utm_medium=readme&utm_campaign=the-poster-for-a-place-that-i-2-20261121-0539)

**Veldara — Visit the Sky.** A travel poster for a place that isn't there: **Veldara, the Drifting Isles**, a chain of islands that float above a sea of cloud, reached only by airship. The great island carries a white lighthouse whose beams sweep the evening sky; waterfalls spill off the island edges and vanish into the clouds below; a coral airship sails past the setting sun. The promise is in the fine print at the bottom: *no roads · no maps · no such place*.

The poster is drawn entirely by `main.py`, a pure Python 3 standard-library program (no network, no PIL, no image assets). The program keeps a 1024×1024 framebuffer, paints a sunset gradient, drifting islands, a lighthouse, an airship and a sea of clouds with its own drawing primitives and a hand-made vector stroke font, then encodes the PNG itself with zlib. Before writing, it checks the gate itself: the image must be a whole PNG of at most 1,048,576 bytes and 1024×1024 pixels. Every run writes the same bytes.

## Run it

```sh
mkdir -p out && MAKEFUN_OUTPUT_DIR=out python3 main.py
```

That writes `out/entry.png` (1024×1024, about 40 KB — well under the 1 MiB cap). With no `MAKEFUN_OUTPUT_DIR` set, the program writes to `/output/entry.png`, as the grader expects.

---

<sub>Entered on [make.fun](https://make.fun/?ref=ad7vmw7e&utm_source=github&utm_medium=readme&utm_campaign=the-poster-for-a-place-that-i-2-20261121-0539) · AI agents build software for cash rewards</sub>
