# Deterministic Slide Translate Plan

## Goal

Replace the current per-image prompt-only `Slide Translate` behavior with a two-pass, deck-level glossary workflow that makes slide translation as deterministic and repeatable as possible.

The target behavior is:

1. Extract all visible text from a presentation once.
2. Build a frozen glossary for that presentation.
3. Apply that glossary slide-by-slide in a deterministic render pass.
4. Avoid per-slide wording drift caused by image-to-image translation without context.

This plan is for **slide image translation only**. It is separate from:

1. transcript translation
2. text translation memory / termbase used for transcript/TTS
3. TTS and video export


## Current State

The current slide translation step is:

- `scripts/providers/translate_final_slides_gemini.py`

Current behavior:

1. Takes already cleaned final slides from `final/slide`
2. Sends each image independently to a Gemini image model
3. Uses:
   - `config/prompts/gemini_translate_prompt.txt`
   - `config/language/translation_termbase.csv` as prompt glossary hints
4. Writes output to `final/slide_translated`

Current weakness:

1. Each slide is translated independently.
2. The model has no deck-level memory.
3. Prompt glossary helps but is not deterministic.
4. The same source phrase can drift across slides.


## Target Architecture

The new workflow is a **two-pass deck-level system**.

### Pass 1: Build Deck Glossary

Run once per deck / run.

For every translatable slide:

1. OCR all text fragments
2. Normalize the extracted text
3. Collect unique strings
4. Translate each unique string once
5. Freeze the mapping into a deck-local glossary

Output:

- `slitranet/slide_translate/glossary.json`
- `slitranet/slide_translate/glossary.csv`
- `slitranet/slide_translate/ocr_pass1.json`
- `slitranet/slide_translate/ocr_pass1.csv`

### Pass 2: Apply Deck Glossary

Run per slide.

For every translated slide:

1. OCR slide again
2. Normalize extracted fragments
3. Look up each fragment in the frozen deck glossary
4. Remove original text region
5. Render translated text back into the same region

Output:

- `slitranet/keyframes/final/slide_translated`
- `slitranet/slide_translate/apply_manifest.json`
- `slitranet/slide_translate/apply_manifest.csv`
- optional debug outputs


## High-Level Design Decisions

### 1. Do not use image-to-image translation for the final deterministic pass

The current Gemini image-to-image model can still be used as an optional helper during glossary creation, but it should not be the final source of truth for per-slide wording.

The deterministic final pass should be:

1. OCR
2. glossary lookup
3. erase original text
4. render translated text

That is the only way to guarantee:

- same source string => same translated string

### 2. Use a deck-local glossary, not only the global termbase

The existing global termbase:

- `config/language/translation_termbase.csv`

should remain for fixed terminology.

But the new slide translation pass needs a second layer:

- **deck glossary**

This deck glossary is generated once per run/deck and frozen before rendering starts.

### 3. OCR and render must be deterministic

The final output should not depend on a creative image model after the glossary has been frozen.


## Proposed New Pipeline Position

Current relevant order:

1. `Finalize Slides`
2. `Slide Edit`
3. `Slide Translate`
4. `Slide Upscale`

Proposed future order:

1. `Finalize Slides`
2. `Slide Edit`
3. `Slide Translate - Build Glossary`
4. `Slide Translate - Apply Glossary`
5. `Slide Upscale`

In the UI this can still appear as a single `Slide Translate` step initially, but internally it should become two explicit substeps.


## Pass 1: Build Deck Glossary

### Input

Preferred source:

1. `slitranet/keyframes/final/slide`

Optional later:

1. `slide_clean` or other variants if needed

### OCR provider

Recommended first implementation:

1. Google Cloud Vision
2. `DOCUMENT_TEXT_DETECTION`

Reason:

1. Slides are structured text, not natural photos.
2. We already considered Cloud Vision elsewhere.
3. The OCR quality is more important here than keeping this step fully local.

### OCR output per fragment

Each OCR fragment should store:

1. `slide_index`
2. `event_id`
3. `fragment_id`
4. `text_raw`
5. `text_norm`
6. `bbox`
   - `x`
   - `y`
   - `w`
   - `h`
7. `confidence`
8. `line_id`
9. `block_id`

### Text normalization rules

Normalization must be shared by both passes.

Implement one helper module, e.g.:

- `scripts/lib/slide_text_normalization.py`

Rules:

1. trim leading/trailing whitespace
2. collapse repeated internal whitespace to one space
3. normalize Unicode to NFKC
4. normalize smart quotes to simple quotes if desired
5. normalize line breaks into spaces
6. preserve case by default
7. optionally keep punctuation

Important:

The normalization rules used to build the glossary must be **identical** to the rules used during application.

### Unique string collection

From all OCR fragments:

1. group by `text_norm`
2. preserve representative source examples
3. count occurrences
4. store which slides use each string

Output:

- `glossary_candidates.json`
- `glossary_candidates.csv`

### Translation of glossary candidates

For each unique candidate:

1. first check the global termbase
2. if exact termbase hit exists for the selected target language:
   - use that target text directly
3. otherwise call a translator once for the candidate

Preferred first implementation:

1. Google Cloud Translation LLM
2. same target language as transcript translation

Store:

1. `source_text`
2. `source_text_norm`
3. `target_text`
4. `target_language`
5. `origin`
   - `termbase`
   - `llm`
6. `status`
   - `frozen`
   - later maybe `reviewed`

### Frozen deck glossary output

New deck-local artifact:

- `slitranet/slide_translate/glossary.json`
- `slitranet/slide_translate/glossary.csv`

This file is immutable for the rest of the run.

No automatic updates after Pass 1.


## Pass 2: Apply Deck Glossary

### Input

1. original slide image
2. OCR fragments for that slide
3. frozen deck glossary

### Lookup behavior

For each OCR fragment:

1. normalize text
2. exact glossary lookup on `text_norm`
3. if found:
   - use exact frozen target string
4. if not found:
   - mark as unresolved
   - add to `needs_review`
   - do **not** send the whole image through a creative fallback in the deterministic path

Important:

The deterministic path should not silently invent a translation.

### Original text removal

For each OCR box:

1. compute mask for the original text region
2. inpaint / fill the region

Recommended first approach:

1. background fill from surrounding pixels
2. light inpainting only for the text area

This should be local OpenCV logic, not generative.

### Render translated text back into the box

New helper module:

- `scripts/lib/slide_text_render.py`

Responsibilities:

1. choose font size to fit the OCR box
2. wrap translated text within the same box width
3. preserve line alignment as much as possible
4. choose text color from original OCR region if possible
5. handle overflow deterministically

Recommended rule:

1. shrink font until the target text fits
2. if still impossible:
   - mark slide as `needs_review`
   - do not clip silently

### Output artifacts

1. translated images:
   - `slitranet/keyframes/final/slide_translated`
2. per-slide manifest:
   - `slitranet/slide_translate/apply_manifest.json`
   - `slitranet/slide_translate/apply_manifest.csv`
3. debug:
   - `slitranet/slide_translate/debug/boxes`
   - `slitranet/slide_translate/debug/masks`
   - `slitranet/slide_translate/debug/overlay`
4. unresolved cases:
   - `slitranet/slide_translate/needs_review.json`


## New Suggested File Structure

### New scripts

1. `scripts/pipeline/build_slide_translate_glossary.py`
2. `scripts/pipeline/apply_slide_translate_glossary.py`

### New libs

1. `scripts/lib/slide_text_normalization.py`
2. `scripts/lib/slide_ocr.py`
3. `scripts/lib/slide_text_render.py`
4. optional:
   - `scripts/lib/slide_glossary.py`

### New output folder

Per run:

- `output/runs/<run_id>/slitranet/slide_translate/`

Contents:

1. `ocr_pass1.json`
2. `ocr_pass1.csv`
3. `glossary_candidates.json`
4. `glossary_candidates.csv`
5. `glossary.json`
6. `glossary.csv`
7. `apply_manifest.json`
8. `apply_manifest.csv`
9. `needs_review.json`
10. optional `debug/`


## Integration With Existing Project Concepts

### Global termbase

Existing:

- `config/language/translation_termbase.csv`

Use it in Pass 1 as the highest-priority deterministic source:

1. if OCR text exactly matches a termbase source
2. and target language matches
3. use the termbase target directly

### Existing transcript translation memory

Do **not** reuse transcript TM directly as the primary source for slide text.

Reason:

1. transcript text and visible slide text are different domains
2. transcript TM works at segment/sentence level
3. slide glossary must work at OCR-fragment level

### Optional future extension

After the deck glossary is created, it may optionally be added back to the global termbase or a separate persistent slide glossary store.

Not needed for Phase 1.


## API / Cloud Requirements

### Google Cloud Vision

New config:

1. `GOOGLE_VISION_PROJECT_ID`
2. `GOOGLE_VISION_LOCATION` if needed by client flow
3. `GOOGLE_VISION_FEATURE=DOCUMENT_TEXT_DETECTION`

ADC requirements:

1. `vision.googleapis.com` enabled
2. valid ADC
3. quota project configured

### Google Cloud Translation LLM

Reuse existing config:

1. `GOOGLE_TRANSLATE_PROJECT_ID`
2. `GOOGLE_TRANSLATE_LOCATION`
3. `GOOGLE_TRANSLATE_MODEL`
4. `GOOGLE_TRANSLATE_SOURCE_LANGUAGE_CODE`


## UI / Settings Changes

### Settings

Keep `Slide Translate` as the visible step, but add grouped settings such as:

1. `SLIDE_TRANSLATE_PROVIDER`
   - `gemini_image`
   - `deterministic_glossary`
2. `SLIDE_TRANSLATE_OCR_PROVIDER`
   - `google_vision`
3. `SLIDE_TRANSLATE_BUILD_GLOSSARY`
   - toggle
4. `SLIDE_TRANSLATE_APPLY_GLOSSARY`
   - toggle
5. `SLIDE_TRANSLATE_NEEDS_REVIEW_POLICY`
   - `allow_partial`
   - `mark_only`

### New API tests

Potentially add:

1. `Slide OCR API Test`
2. `Slide Glossary Translation API Test`

These should be distinct from the current slide translate image-model health check.


## Implementation Phases

## Phase 1: Foundation

Goal:

1. build OCR + glossary artifacts
2. do not replace the existing image-to-image slide translation yet

Tasks:

1. implement `slide_text_normalization.py`
2. implement `slide_ocr.py` with Cloud Vision OCR
3. implement `build_slide_translate_glossary.py`
4. write:
   - `ocr_pass1.*`
   - `glossary_candidates.*`
   - `glossary.*`
5. add new config fields
6. add health check(s)

Acceptance:

1. a run can generate a stable deck glossary
2. repeated OCR strings map to one frozen target string

## Phase 2: Deterministic Apply Pass

Goal:

1. translate slides by rendering text from the frozen glossary
2. still keep the old Gemini image translate path as fallback option

Tasks:

1. implement `slide_text_render.py`
2. implement `apply_slide_translate_glossary.py`
3. write translated slides into a separate folder first:
   - `slide_translated_glossary`
4. produce `apply_manifest.*`
5. produce `needs_review.json`

Acceptance:

1. same source OCR fragment always yields the same target string
2. visual output is stable across repeated runs

## Phase 3: Replace Current Slide Translate Default

Goal:

1. make deterministic glossary translation the default `Slide Translate` mode
2. keep Gemini image translate only as an explicit alternative

Tasks:

1. switch pipeline default
2. wire UI accordingly
3. update export/input image source priority if needed

Acceptance:

1. per-slide wording drift disappears
2. outputs are reproducible from the same glossary

## Phase 4: Review Workflow

Goal:

1. allow manual corrections to the frozen deck glossary
2. rerender without rebuilding the rest of the pipeline

Tasks:

1. make glossary downloadable/editable
2. add re-apply command
3. make `needs_review` actionable


## Concrete Code Change Map

### Replace / bypass current slide translate path

Current file:

- `scripts/providers/translate_final_slides_gemini.py`

Proposed:

1. keep this file as:
   - `legacy_gemini_slide_translate`
2. new pipeline route:
   - `build_slide_translate_glossary.py`
   - `apply_slide_translate_glossary.py`

### Update pipeline orchestration

Current:

- `scripts/run_pipeline.sh`

Needed:

1. add substeps under `Slide Translate`
2. new step detail logs
3. atomic publish of `slide_translated`

### Update server/UI

Current:

- `web/server.py`
- `web/js/settings.js`
- `web/index.html`

Needed:

1. new config keys
2. health checks
3. optional debug/download links


## Matching Rules and Determinism Requirements

These rules are mandatory for the implementation.

1. **Exact normalized string match**
   - no semantic guessing in the apply pass

2. **Frozen glossary**
   - no silent updates during pass 2

3. **No creative fallback in deterministic mode**
   - unresolved fragments go to `needs_review`

4. **Stable rendering**
   - same input image + same glossary => same output image

5. **Explicit provenance**
   - every glossary row should know whether it came from:
     - termbase
     - translation-llm


## Risks

### 1. OCR granularity

Cloud Vision may split text differently across slides.

Mitigation:

1. store raw OCR hierarchy
2. normalize fragment joining rules
3. keep line/block IDs

### 2. Text rendering fit

Some translations will be longer than source text.

Mitigation:

1. deterministic font shrink
2. explicit `needs_review` when overflow persists

### 3. Visual background cleanup

Removing text from the original slide may leave artifacts.

Mitigation:

1. use conservative local fill
2. keep debug overlays

### 4. OCR mistakes

Bad OCR can poison the glossary.

Mitigation:

1. keep `confidence`
2. keep candidates/debug exports
3. make glossary reviewable


## Recommended Implementation Order

1. `slide_text_normalization.py`
2. `slide_ocr.py`
3. `build_slide_translate_glossary.py`
4. save glossary/debug artifacts
5. `apply_slide_translate_glossary.py`
6. deterministic rendering
7. wire into `run_pipeline.sh`
8. add settings / health checks
9. expose glossary + review artifacts in UI


## Acceptance Criteria

The new deterministic slide translate workflow is successful when:

1. repeated source OCR strings across a deck always map to the same target string
2. the generated glossary is frozen per deck
3. translated slide images are reproducible across reruns
4. unresolved strings are explicit and reviewable
5. the old per-image wording drift is no longer visible in the exported deck

