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

## Phase 2: Backend Expansion ✅

**Completed:**
- [x] Add `POST /api/upload-video` route to `server.py`
  - Receives multipart video file upload
  - Creates job with uuid, saves file
  - Returns job_id for polling
- [x] Add `GET /api/video-jobs/<job_id>` route
  - Polls video processing status
  - Returns status, logs, output_dir on completion
- [x] Implement `run_video_job()` function
  - Spawns subprocess: `video_processor/generate.py`
  - Redirects stdout/stderr to log.txt
  - Handles timeouts and errors
- [x] Add `GET /jobs/<job_id>/video-output/<path>` route
  - Serves video processing outputs (metadata.json, thumbs, etc.)
  - Guard against path traversal
- [x] Import `secure_filename` from werkzeug
  - Sanitizes uploaded filenames

**New Routes Summary:**
```
POST   /api/upload-video           → submit video, get job_id
GET    /api/video-jobs/&lt;id&gt;      → poll status, get output_dir
GET    /jobs/&lt;id&gt;/video-output/&lt;path&gt; → serve processed files
```

---

## Phase 3: Frontend Tabs & Forms ✅

**Completed:**
- [x] Modified `templates/index.html` to add tab structure
  - Added `.tabs-header` with tab buttons
  - Wrapped composition form in `#tab-composition`
  - Created new `#tab-video` with video upload form
- [x] Added video upload form (Tab 1)
  - File input with video/* accept
  - Status section with badge, logs, error area
  - "Use in Composition" button
- [x] Updated `static/style.css` with tab styling
  - `.tabs-header` and `.tab-button` styles
  - `.tab-button.active` state
  - Fade-in animation for tab content
  - Responsive overflow handling
- [x] Updated `static/app.js` with tab logic
  - `switchTab()` function for tab switching
  - Video form submission handler
  - `pollVideoStatus()` for video job polling
  - `formatVideoStatus()` for status display
  - "Use video output" button integration
  - Both composition and video jobs can run independently

---

## Phase 4: Form Linking & State ✅

**Completed:**
- [x] Implemented "Use this output in Tab 2" button
  - Button appears when video job completes
  - On click: fills `#folder` input with video output path
  - Switches to Tab 2 (composition)
  - Scrolls to folder field
- [x] State handoff Tab 1 → Tab 2
  - `lastVideoOutput` variable stores path
  - Single event listener avoids duplicates
  - User can immediately enter lyrics and submit
- [x] Verified form independence
  - Tab 1 can run without Tab 2
  - Tab 2 can run without Tab 1
  - Both can chain (video output → composition)

---

## Phase 5: Testing ✅

**Verified (user confirmed working):**
- [x] Scenario 1: Video upload + processing (Tab 1)
- [x] Scenario 2: Direct folder composition (Tab 2 with existing folder)
- [x] Scenario 3: Two-stage (Tab 1 → Tab 2 auto-handoff)
- [x] Scenario 4: Backward compatibility (CLI still works)
- [x] All integration tests passed

---

## Phase 6: Documentation ✅

**Completed:**
- [x] Updated README.md (Spanish)
  - Emphasized two-tab integrated interface
  - Added "Flujos de uso comunes" (A, B, C)
  - Clarified web flow vs CLI flow
  - Updated requirements section
- [x] Updated FLOW.md (Spanish)
  - New "Flujo integrado" section with Tab A (Video → Composición)
  - New "Flujo B" (existing folder → composition)
  - Moved CLI workflows to "Escenario antiguo"
  - Updated browser flow diagram with both tabs
  - Updated real-world use case example
  - Added advantages of integrated approach

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

---

## 🎉 Integration Complete!

All 6 phases finished and tested. The selector-fotogramas → creador-contenido unification is **production-ready**:

✅ Files integrated (Phase 1)  
✅ Backend routes added (Phase 2)  
✅ Frontend tabs implemented (Phase 3)  
✅ Form state linking works (Phase 4)  
✅ All workflows tested (Phase 5)  
✅ Documentation updated (Phase 6)  

**Ready to use:** `python3 server.py` → http://localhost:5000
