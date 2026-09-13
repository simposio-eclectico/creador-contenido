# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Creador de Contenido** is a two-stage content creation system that turns video frames into social media posts:

1. **Input:** A folder of images (with `metadata.json` containing OpenCLIP embeddings from selector-fotogramas) + a lyrics file
2. **Process:** Matches each lyric line to the best-fitting images using semantic similarity (CLIP embeddings), then composes them for a target format
3. **Output:** `review.html` — an interactive editor where users can select images, choose typography, colors, and effects; plus `associations.json` (all candidates per line with scores)

## Quick Start

```bash
./run.sh                  # Start the web server (http://localhost:5000)
```

Or manually:
```bash
python3 -m pip install -r requirements.txt
python3 server.py
```

## Architecture at a Glance

### Stack
- **Backend:** Flask (`server.py`) — orchestrates jobs, validates input, spawns subprocess chains
- **Frontend:** Vanilla JS (`static/app.js`), no frameworks — polls for job status, displays live logs
- **Processing:** Two independent CLI scripts wired together by the backend:
  - `generate_from_folder.py` — processes raw image folders into embeddings + clustering (if needed)
  - `main.py` — matches lyrics to images, composes for target format

### Job Flow

```
User submits form → POST /api/jobs
    ↓
Backend: spawn background thread
    ↓
Does folder have metadata.json?
    ├─ NO  → run generate_from_folder.py (only once per folder)
    └─ YES → skip, go straight to main.py
    ↓
main.py → compose + write review.html + associations.json
    ↓
Frontend polls GET /api/jobs/<id>, shows live log
    ↓
On completion → reveal link to /jobs/<id>/review/review.html
```

### Key Files

| File | Purpose |
|------|---------|
| `server.py` | Flask app; routes: `/` (form), `/api/jobs` (POST), `/api/jobs/<id>` (GET status), `/api/browse` (folder picker), `/jobs/<id>/review/<path>` (serve results) |
| `main.py` | CLI: takes images folder + lyrics → writes review.html + associations.json |
| `generate_from_folder.py` | CLI: takes raw image folder → extracts frames, computes embeddings, clusters duplicates |
| `templates/index.html` | Web form: folder input, lyrics textarea/file, format selector, advanced options |
| `static/app.js` | Polls job status every 1.5s, updates UI, handles form submit |
| `lyrics_social/` | Module suite: matching (CLIP similarity), composer (image cropping + text placement), review (HTML generation), images (loading), lyrics (parsing), text_embeddings |

### `lyrics_social/` Modules

- **`matching.py`** — `rank_candidates()` (CLIP similarity), `all_candidates()` (no ranking, manual mode)
  - **Extension point:** `classify_relation()` currently always returns `"semantica"` (literal/semantic); design expected to call an LLM here for associative/contrapunto relations
- **`composer.py`** — Crops images to format, places text zone avoiding detected faces (field `face_position` from metadata.json)
- **`review.py`** — Generates `review.html` (canvas-based editor, live preview, exports PNG)
- **`images.py`** — Loads image library from metadata.json + embeddings
- **`text_embeddings.py`** — Computes CLIP embeddings for lyrics using the same OpenCLIP model as selector-fotogramas (ViT-B-32)

### State on Disk

```
jobs/                              (gitignored; temp per-job state)
  <job_id>/
    log.txt                        (stdout + stderr from both subprocesses)
    lyrics.txt                     (lyrics pasted by user)
    generate_output/               (only if generate_from_folder ran)
      thumbs/, full/, metadata.json, metadata.js, ...
    main_output/                   (final result)
      review.html                  (interactive editor)
      associations.json            (candidates per line + metadata)
      compositions/, backgrounds/, sources/
```

## Common Development Tasks

### Running the Web Server
```bash
./run.sh
# or: python3 server.py
```
Then open http://localhost:5000 in your browser.

### Running CLI Tools Directly
```bash
# Process raw images → metadata.json + embeddings
python3 generate_from_folder.py --input ./raw-photos --output ./processed

# Compose lyrics + images → review.html
python3 main.py --images ./processed --lyrics lyrics.txt --format instagram_4_5
```

### Testing a Feature

If modifying `lyrics_social/composer.py` (image cropping/text placement):
```bash
python3 main.py --images /path/to/folder --lyrics test.txt --format instagram_4_5 --output ./test-output
# Then open ./test-output/review.html in browser
```

If modifying `server.py` or `static/app.js`:
- Restart the server: kill it (Ctrl+C), re-run `./run.sh`
- Browser auto-reloads on most changes (check network tab if stale)

## Important Implementation Details

### OpenCLIP Model
The entire system uses **OpenCLIP ViT-B-32** (pretrained on LAION 2B) for consistency:
- Selector-fotogramas computes image embeddings during video processing
- Creador-contenido reuses those embeddings + computes text embeddings on the fly
- Avoid changing the model string; if you do, existing metadata.json files become incompatible

### Favorites / Manual Filtering
Users can export favorites from selector-fotogramas' viewer as a JSON backup and pass it to main.py via `--favorites`:
```bash
python3 main.py --images ./folder --lyrics letter.txt --favorites ./respaldo.json
```
This filters `metadata.json` frames to only those marked as favorites.

### Selection Modes
- **`auto` (default):** Ranks images per line by CLIP similarity, keeps top-k candidates
- **`manual`:** Shows all images as candidates in all lines (no ranking); reuses selector-fotogramas' thumbnails to avoid composing all combinatorial permutations

### Job State Machine
```
pending → running_generate → running_main → done
                          ↘                    ↗
                             error (any step)
```
Each status change updates `JOBS[job_id]` under `JOBS_LOCK`.

### Security Notes
- **Path traversal guard:** `/jobs/<id>/review/<path>` validates `target.is_relative_to(base)` before serving
- **Command injection:** All subprocess args passed as lists, never shell=True
- **Job isolation:** Each job has unique UUID, own directory; can run in parallel (daemon threads)
- **Input validation:** Folder existence + is_dir; lyrics non-empty; favorites path existence check

## Integration: selector-fotogramas Unification (Complete)

The system was unified with selector-fotogramas via a multi-tab interface:
- **Tab 1 (Composición):** Frames + lyrics → compositions (original creador-contenido flow)
- **Tab 2 (Video):** Video → frames (selector-fotogramas, integrated)
- **Tab 3 (Reels):** Video → highlight clips with subtitles (see below)

**What changed:**
- `video_processor/` subdirectory contains selector-fotogramas' code:
  - `video_processor/generate.py` — video processing CLI
  - `video_processor/viewer/` — frame browser UI
- `.gitignore` updated to ignore video files and test outputs
- See `INTEGRATION.md` for the full phase-by-phase history

**Backward compatible:** all CLI tools (`main.py`, `generate_from_folder.py`) and existing web routes work unchanged.

## Reel Extraction (`reel_extractor/`)

**Tab 3** takes a video and extracts the N most "important" moments as short vertical clips ("reels"), optionally with burned-in subtitles.

**Pipeline (`reel_extractor/extract.py`):**
1. Extract audio → compute RMS energy + spectral flux score per time window (`audio_signal.py`)
2. Sample video at low fps → compute entropy + contrast + saliency + **motion** (frame-to-frame diff) score (`visual_signal.py`)
3. Combine both signals on a common time grid using `--audio-weight` (0=visual only, 1=audio only), then greedily pick N non-overlapping windows of `--duration` seconds that maximize the combined score (`highlight.py`)
4. Render each window as a vertical clip (`story` 1080x1920 or `square` 1080x1080) via ffmpeg center-crop + scale (`clip_render.py`)
5. Optionally apply a fadeout (`--fade-out` seconds) of audio + video at the end of each clip, either to black or dissolving into a fixed image (`clip_render.py::apply_fade`)
6. If `--subtitles`: transcribe the **full video once** with local Whisper (`transcribe.py`, language selectable via `--language`), then per-window filter/re-zero segments into a `.srt`. The web flow always passes `--skip-burn` here — burning happens in a separate confirmation step (below) so the user can review/edit the transcribed text first; direct CLI use without `--skip-burn` burns immediately with the raw Whisper output, same as before.

**Two-stage subtitle review (web only):**
- `POST /api/upload-reel-video` → `run_reel_job()` calls `extract.py --subtitles --skip-burn`. This renders all clips (sin subtítulos, always available as `reel["clip"]`) and writes each reel's Whisper segments into `metadata.json` (`reel["segments"]`), but does **not** burn anything. Job status becomes `awaiting_review` instead of `done`.
- Frontend (`renderReelReview()` in `app.js`) shows each reel's plain clip next to an editable textarea per transcribed segment.
- `POST /api/reel-jobs/<id>/confirm-subtitles` with `{"reels": [{"id", "segments": [{"start","end","text"}]}]}` (edited or not) → `run_burn_subtitles_job()` invokes `reel_extractor/burn_subs.py` once per reel — a standalone script that only burns + rewrites the `.srt`, without re-running highlight detection or transcription (both expensive). Job status becomes `done`, with `clip_with_subtitles` now pointing at the burned version reflecting the edited text.
- The un-subtitled clip (`reel["clip"]`) is generated unconditionally regardless of `--subtitles` — the gallery always offers a "sin subtítulos" download alongside the burned one.

**Key design decisions:**
- Uses `openai-whisper` (not faster-whisper) — reuses the `torch` install already required for OpenCLIP, no second heavy runtime
- Transcribes once on the full video, not per-clip — Whisper's model-load overhead dominates for short clips, and timestamps are already absolute so slicing per-window is just an offset/filter operation
- Subtitle burn-in uses **`drawtext`, not the `subtitles` filter** — both require `libfreetype`/`libass` respectively, which the *default* Homebrew `ffmpeg` formula does not compile in. **Fix: `brew install ffmpeg-full`** (keg-only, doesn't replace the default `ffmpeg`) — it bundles both. `reel_extractor/_ffmpeg_utils.py::_resolve_binary()` auto-detects `ffmpeg-full` at its Homebrew path (`/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg`) and prefers it over the plain `ffmpeg` on PATH; override with `REEL_FFMPEG_BIN`/`REEL_FFPROBE_BIN` env vars if installed elsewhere. If neither build is found, `extract.py` degrades gracefully: it logs a warning and keeps the `.srt` file, skipping only the burned-in version
- Subtitle font is selectable (`--subtitle-font`, catalog in `reel_extractor/fonts.py`), default **IM Fell DW Pica** — same family as `lyrics_social/review.py`'s canvas text, vendored as a real `.ttf` under `reel_extractor/fonts/` (SIL OFL license) since `drawtext` needs an actual font file, not a CSS font stack
- `reel_extractor/_ffmpeg_utils.py` duplicates `run()`/`probe_duration()` from `video_processor/generate.py` rather than importing across sibling packages (avoids sys.path coupling between independently-invokable CLI tools)
- `probe_video_size()` parses ffprobe's `-of json` output (not `csv`) — some videos add extra columns to the csv format (e.g. rotation side-data) that broke a fixed 2-value unpack
- If the video is shorter than the requested duration, or fewer non-overlapping windows exist than `--count`, the pipeline returns what it can find and logs a warning rather than failing

**CLI:**
```bash
python3 reel_extractor/extract.py --input video.mp4 --output ./reels_output \
  --duration 30 --count 3 --audio-weight 0.5 --format story \
  --subtitles --whisper-model base --subtitle-font im_fell \
  --fade-out 3 --fade-target image --fade-image outro.png
```

**Backend routes:** `POST /api/upload-reel-video`, `GET /api/reel-jobs/<id>`, `POST /api/reel-jobs/<id>/confirm-subtitles`, `GET /jobs/<id>/reel-output/<path>` — same job orchestration pattern (`threading.Thread` + `JOBS` dict) as Tab 2's video processing. The upload route also accepts an optional `fade_image` file field for `fade_target=image`. Job state machine when subtitles are on: `pending → processing → awaiting_review → processing → done`.

**Gotcha hit during development:** when testing manually with a background server process, always confirm you killed the *previous* instance before starting a new one — Flask's dev server fails to bind a busy port and prints "Address already in use" to its own log without crashing the shell job, so stale requests silently hit old code. Check with `lsof -ti:5000` before assuming a fresh start.

## Extending the Matching Algorithm

The current matching is **semantic only** (CLIP similarity rank). To add **associative** or **contrapunto** relations:

1. Modify `lyrics_social/matching.py::classify_relation()` to call an LLM (e.g., Claude, GPT) with:
   - `lyrics_line` (the text)
   - `candidate_images` (filenames or descriptions)
2. Reorder / re-score candidates based on LLM classification
3. Update the `relation` field in `associations.json` per candidate

This is an explicit extension point in the design.

## Debugging Tips

**"Job runs but metadata.json not found"**
- Check that your input folder actually has metadata.json or has permissions
- If raw images, ensure generate_from_folder.py finishes without error (check log.txt)

**"CLIP embedding takes forever"**
- Text embeddings computed on-the-fly; can be slow on CPU
- Pass `--device cuda` or `--device mps` if available
- Image embeddings already cached in metadata.json (fast)

**"review.html shows wrong image for a line"**
- Likely semantic mismatch or too-low top-k
- Try `--selection-mode manual` to browse all candidates interactively
- Or reduce `--cluster-eps` in generate_from_folder to get more diverse images

**"Canvas rendering wrong in review.html"**
- Check `face_position` is valid in metadata.json (should be [x, y] or null)
- Verify format config in `lyrics_social/composer.py::FORMATS` matches the format you selected

**"Reels generate but subtitles aren't burned in (only .srt appears)"**
- Your ffmpeg build lacks `drawtext` (needs libfreetype). Check with `ffmpeg -filters | grep draw`
- Fix: `brew install ffmpeg-full` — `reel_extractor` auto-detects and prefers it over plain `ffmpeg`
- This is a graceful degradation, not a bug — the job still completes and the `.srt` is usable standalone even without the fix

**"Whisper produces repetitive/nonsense subtitles"**
- Usually means low audio quality or the `tiny` model on ambiguous audio — try `--whisper-model base` or `small`
- Synthetic/TTS audio can trigger repetition loops in Whisper more than natural speech

## Dependencies

See `requirements.txt`:
- `torch` ≥2.1 (heavy)
- `open_clip_torch` ≥2.24
- `openai-whisper` ≥20231117 (reel subtitles; reuses the `torch` install above)
- `Pillow` ≥10.0
- `scipy`, `scikit-learn` (clustering, image metrics)
- `opencv-contrib-python` (face detection)
- `Flask` ≥3.0
- System binary: `ffmpeg`/`ffprobe` (video processing + reel rendering)
  - Recommended: `brew install ffmpeg-full` for burned-in subtitle support (`drawtext`/`subtitles` filters, needs libfreetype/libass) — auto-detected if present, see Reel Extraction section above

No dev dependencies (tests, linters) yet — contributions welcome.

## Contact & Contribution

- Repository: creador-contenido (main branch recommended for PRs)
- Upsteam dependency: selector-fotogramas (video → metadata.json)
- Author: Cristóbal Ramos (cristobal.ramos@autodesk.com)
