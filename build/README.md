# build

`make.py` draws every SVG in `assets/` (light and dark) with the portfolio's fonts embedded as subsets.

```bash
pip install fonttools brotli
python3 build/make.py
```

Project data lives in the `PROJECTS` list at the top of the file — edit it there and re-run.
Fonts in `fonts/` are Fraunces, Inter and JetBrains Mono (SIL Open Font License).
