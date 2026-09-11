# Integration: selector-fotogramas → creador-contenido

This document tracks the unification of selector-fotogramas into creador-contenido with a two-tab web interface.

**Status:** Phase 1 ✅ Complete | Phase 2 → Pending

---

## Phase 1: Setup & File Movement ✅

**Completed:**
- [x] Created `video_processor/` directory
- [x] Copied `generate.py` from selector-fotogramas
- [x] Copied `viewer/` (HTML, JS, CSS) from selector-fotogramas
- [x] Created `video_processor/__init__.py` (marks as package)
- [x] Verified generate.py paths work in new location
  - `SCRIPT_DIR = Path(__file__).resolve().parent` ✓ (automatically resolves correctly)
  - `VIEWER_DIR = SCRIPT_DIR / "viewer"` ✓ (relative path works)
- [x] Updated `.gitignore`:
  - Ignores `jobs/` (all job outputs)
  - Ignores `video_processor/test_output/` (test videos)
  - Ignores video file formats (`*.mp4`, `*.mkv`, `*.mov`)

**Directory structure (verified):**
```
creador-contenido/
└── video_processor/
    ├── __init__.py
    ├── generate.py (16.2 KB)
    └── viewer/
        ├── index.html (2.9 KB)
        ├── app.js (21.5 KB)
        └── style.css (4.6 KB)
```

**Next:** Phase 2 - Backend expansion (new routes in server.py)

---

## Phase 2: Backend Expansion (TODO)

Tasks:
- [ ] Add `POST /api/upload-video` route to `server.py`
- [ ] Add `GET /api/video-jobs/<job_id>` route
- [ ] Implement `run_video_job()` function
- [ ] Test video processing subprocess calls
- [ ] Verify file upload handling

---

## Phase 3: Frontend Tabs & Forms (TODO)

Tasks:
- [ ] Modify `templates/index.html` to add tab structure
- [ ] Extract existing form into tab content
- [ ] Add video upload form (Tab 1)
- [ ] Add tab switching styles + animations
- [ ] Update `static/app.js` with tab logic
- [ ] Update `static/style.css` for tab styling

---

## Phase 4: Form Linking & State (TODO)

Tasks:
- [ ] Implement "Use this output in Tab 2" button logic
- [ ] Auto-populate folder field when video job completes
- [ ] Test state handoff Tab 1 → Tab 2

---

## Phase 5: Testing (TODO)

Tasks:
- [ ] Scenario 1: Video-only workflow (Tab 1)
- [ ] Scenario 2: Direct composition (Tab 2 with existing folder)
- [ ] Scenario 3: Two-stage (Tab 1 → Tab 2)
- [ ] Scenario 4: Backward compatibility (old CLI workflows)
- [ ] Error handling (invalid video, network errors)

---

## Phase 6: Documentation (TODO)

Tasks:
- [ ] Update README.md with two-tab flow
- [ ] Add usage examples
- [ ] Document new API routes
- [ ] Update FLOW.md

---

## Important: No Breaking Changes

The following remain unchanged and fully functional:
- ✅ CLI: `python3 main.py --images ./folder --lyrics letter.txt`
- ✅ CLI: `python3 generate_from_folder.py --input ./raw --output ./out`
- ✅ selector-fotogramas as standalone: `video_processor/generate.py --input video.mp4 --output ./out`
- ✅ Web server without video (direct folder + lyrics path)

---

## Notes

- Both projects use **identical dependencies** (torch, open_clip_torch, Pillow, opencv, scipy, scikit-learn)
- Both use **OpenCLIP ViT-B-32** for embeddings consistency
- `generate.py` uses relative paths via `Path(__file__).resolve().parent` — no code changes needed
- All outputs continue to go into `jobs/<job_id>/` directory structure
