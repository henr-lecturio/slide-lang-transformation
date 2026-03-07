<template>
  <section class="card">
    <div v-if="authResultMsg" :class="['gdrive-auth-result', authResultOk ? 'is-ok' : 'is-error']">
      {{ authResultMsg }}
    </div>

    <!-- Global Main Block -->
    <section class="settings-global-block" aria-label="Main settings">
      <div class="settings-global-head">Main</div>
      <div class="settings-list settings-global-list">
        <div class="settings-row">
          <label class="settings-key">Google Cloud Auth</label>
          <div class="settings-value gdrive-auth-row">
            <span v-if="gcloudLoading" class="gdrive-auth-label is-loading"><span class="auth-spinner"></span> Checking...</span>
            <span v-else-if="gcloudStatus.configured" class="gdrive-auth-label is-ok">{{ gcloudStatus.email }}</span>
            <span v-else class="gdrive-auth-label is-warning">Not configured</span>
            <a href="/api/gcloud/auth/start" class="btn-sm">
              {{ gcloudStatus.configured ? 'Re-authenticate' : 'Authenticate' }}
            </a>
          </div>
        </div>
        <div class="settings-row">
          <label class="settings-key" for="google_speech_language_codes">GOOGLE_SPEECH_LANGUAGE_CODES</label>
          <div class="settings-value"><input id="google_speech_language_codes" type="text" v-model="f.GOOGLE_SPEECH_LANGUAGE_CODES" /></div>
        </div>
        <TtsLanguageSelector
          :options="store.ttsLanguageOptions"
          :model-value="f.GOOGLE_TTS_LANGUAGE_CODE"
          :search-text="store.ttsLanguageSearchText"
          :disabled="!languageSelectionEnabled"
          @update:model-value="onTtsLanguageChange"
          @update:search-text="store.ttsLanguageSearchText = $event"
        />
      </div>
    </section>

    <div class="step-sections">
      <!-- 1. Slide Detection (forced) -->
      <StepSection title="Slide Detection" subtitle="Detects slide changes and exports stable ROI and full-frame keyframes from the source video." :forced="true" v-model:expanded="expanded.slideDetection">
        <div class="settings-list">
          <SettingsRow label="KEYFRAME_SETTLE_FRAMES" field-id="keyframe_settle_frames"><input id="keyframe_settle_frames" type="number" min="0" step="1" v-model="f.KEYFRAME_SETTLE_FRAMES" /></SettingsRow>
          <SettingsRow label="KEYFRAME_STABLE_END_GUARD_FRAMES" field-id="keyframe_stable_end_guard_frames"><input id="keyframe_stable_end_guard_frames" type="number" min="0" step="1" v-model="f.KEYFRAME_STABLE_END_GUARD_FRAMES" /></SettingsRow>
          <SettingsRow label="KEYFRAME_STABLE_LOOKAHEAD_FRAMES" field-id="keyframe_stable_lookahead_frames"><input id="keyframe_stable_lookahead_frames" type="number" min="1" step="1" v-model="f.KEYFRAME_STABLE_LOOKAHEAD_FRAMES" /></SettingsRow>
        </div>
      </StepSection>

      <!-- 2. Transcription (forced) -->
      <StepSection title="Transcription" subtitle="Transcribes the source video into timestamped transcript segments for downstream translation and mapping." :forced="true" v-model:expanded="expanded.transcription">
        <div class="settings-list">
          <SettingsRow label="TRANSCRIPTION_MODEL" field-id="transcription_provider">
            <select id="transcription_provider" v-model="f.TRANSCRIPTION_PROVIDER" @change="onFieldStateChange">
              <option value="whisper">whisper</option>
              <option value="google_chirp_3">google_chirp_3</option>
            </select>
          </SettingsRow>
          <div class="settings-subhead">Whisper</div>
          <SettingsRow label="WHISPER_MODEL" field-id="whisper_model"><input id="whisper_model" type="text" v-model="f.WHISPER_MODEL" :disabled="googleTranscription" /></SettingsRow>
          <SettingsRow label="WHISPER_DEVICE" field-id="whisper_device"><input id="whisper_device" type="text" v-model="f.WHISPER_DEVICE" :disabled="googleTranscription" /></SettingsRow>
          <SettingsRow label="WHISPER_COMPUTE_TYPE" field-id="whisper_compute_type"><input id="whisper_compute_type" type="text" v-model="f.WHISPER_COMPUTE_TYPE" :disabled="googleTranscription" /></SettingsRow>
          <SettingsRow label="WHISPER_LANGUAGE" field-id="whisper_language"><input id="whisper_language" type="text" v-model="f.WHISPER_LANGUAGE" :disabled="googleTranscription" /></SettingsRow>
          <div class="settings-subhead">Google Speech</div>
          <SettingsRow label="GOOGLE_SPEECH_LOCATION" field-id="google_speech_location"><input id="google_speech_location" type="text" v-model="f.GOOGLE_SPEECH_LOCATION" :disabled="!googleTranscription" /></SettingsRow>
          <SettingsRow label="GOOGLE_SPEECH_MODEL" field-id="google_speech_model"><input id="google_speech_model" type="text" v-model="f.GOOGLE_SPEECH_MODEL" :disabled="!googleTranscription" /></SettingsRow>
          <SettingsRow label="GOOGLE_SPEECH_CHUNK_SEC" field-id="google_speech_chunk_sec"><input id="google_speech_chunk_sec" type="number" min="1" step="1" v-model="f.GOOGLE_SPEECH_CHUNK_SEC" :disabled="!googleTranscription" /></SettingsRow>
          <SettingsRow label="GOOGLE_SPEECH_CHUNK_OVERLAP_SEC" field-id="google_speech_chunk_overlap_sec"><input id="google_speech_chunk_overlap_sec" type="number" min="0" step="0.05" v-model="f.GOOGLE_SPEECH_CHUNK_OVERLAP_SEC" :disabled="!googleTranscription" /></SettingsRow>
        </div>
      </StepSection>

      <!-- 3. Transcript Translate -->
      <StepSection title="Transcript Translate" subtitle="Translates transcript segments 1:1 into the target language before slide mapping." v-model:enabled="f.RUN_STEP_TEXT_TRANSLATE" v-model:expanded="expanded.textTranslate" @update:enabled="onFieldStateChange">
        <div class="settings-list">
          <SettingsRow label="GOOGLE_TRANSLATE_LOCATION" field-id="google_translate_location"><input id="google_translate_location" type="text" v-model="f.GOOGLE_TRANSLATE_LOCATION" :disabled="!cloudTranslateConfigEnabled" /></SettingsRow>
          <SettingsRow label="TRANSCRIPT_TRANSLATE_MODEL" field-id="gemini_text_translate_model">
            <select id="gemini_text_translate_model" v-model="f.TRANSCRIPT_TRANSLATE_MODEL" :disabled="!f.RUN_STEP_TEXT_TRANSLATE">
              <option value="gemini-2.5-pro">gemini-2.5-pro</option>
              <option value="general/translation-llm">general/translation-llm</option>
            </select>
          </SettingsRow>
          <SettingsRow label="SOURCE_LANG_CODE" field-id="google_translate_source_language_code"><input id="google_translate_source_language_code" type="text" placeholder="Optional, e.g. en" v-model="f.GOOGLE_TRANSLATE_SOURCE_LANGUAGE_CODE" :disabled="!sourceLanguageConfigEnabled" /></SettingsRow>
          <div class="settings-row settings-row-textarea">
            <label class="settings-key" for="gemini_text_translate_prompt">TRANSCRIPT_TRANSLATE_PROMPT</label>
            <div class="settings-value"><textarea id="gemini_text_translate_prompt" rows="8" v-model="f.GEMINI_TEXT_TRANSLATE_PROMPT" :disabled="!f.RUN_STEP_TEXT_TRANSLATE"></textarea></div>
          </div>
          <div class="settings-row termbase-settings-row">
            <label class="settings-key" for="translation_termbase_csv">TRANSLATION_TERMBASE_CSV</label>
            <div class="settings-value">
              <TermbaseEditor v-model="f.TRANSLATION_TERMBASE_CSV" :language-options="store.ttsLanguageOptions" />
            </div>
          </div>
        </div>
      </StepSection>

      <!-- 4. Transcript Mapping (forced) -->
      <StepSection title="Transcript Mapping" subtitle="Maps transcript segments onto detected slide windows and prepares per-slide text assignments." :forced="true" v-model:expanded="expanded.transcriptMapping">
        <div class="settings-static muted">No separate parameters. This step uses the current transcript output and the current slide changes of the active run.</div>
      </StepSection>

      <!-- 5. Finalize Slides (forced) -->
      <StepSection title="Finalize Slides" subtitle="Speaker filtering and automatic source selection always run." :forced="true" v-model:expanded="expanded.finalizeSlides">
        <div class="settings-list">
          <div class="settings-subhead">Speaker Filter</div>
          <SettingsRow label="SPEAKER_FILTER_MIN_STAGE1_VIDEO_RATIO" field-id="speaker_filter_min_stage1_video_ratio"><input id="speaker_filter_min_stage1_video_ratio" type="number" min="0" max="1" step="0.01" v-model="f.SPEAKER_FILTER_MIN_STAGE1_VIDEO_RATIO" /></SettingsRow>
          <SettingsRow label="SPEAKER_FILTER_MAX_EDGE_DENSITY" field-id="speaker_filter_max_edge_density"><input id="speaker_filter_max_edge_density" type="number" min="0" max="1" step="0.001" v-model="f.SPEAKER_FILTER_MAX_EDGE_DENSITY" /></SettingsRow>
          <SettingsRow label="SPEAKER_FILTER_MAX_LAPLACIAN_VAR" field-id="speaker_filter_max_laplacian_var"><input id="speaker_filter_max_laplacian_var" type="number" min="0" step="1" v-model="f.SPEAKER_FILTER_MAX_LAPLACIAN_VAR" /></SettingsRow>
          <SettingsRow label="SPEAKER_FILTER_MAX_DURATION_SEC" field-id="speaker_filter_max_duration_sec"><input id="speaker_filter_max_duration_sec" type="number" min="0" step="0.1" v-model="f.SPEAKER_FILTER_MAX_DURATION_SEC" /></SettingsRow>
          <div class="settings-subhead">Final Source Auto</div>
          <SettingsRow label="FINAL_SOURCE_MODE_AUTO" field-id="final_source_mode_auto">
            <select id="final_source_mode_auto" v-model="f.FINAL_SOURCE_MODE_AUTO">
              <option value="auto">auto</option>
              <option value="off">off</option>
            </select>
          </SettingsRow>
          <SettingsRow label="FULLSLIDE_SAMPLE_FRAMES" field-id="fullslide_sample_frames"><input id="fullslide_sample_frames" type="number" min="1" step="1" v-model="f.FULLSLIDE_SAMPLE_FRAMES" /></SettingsRow>
          <SettingsRow label="FULLSLIDE_BORDER_STRIP_PX" field-id="fullslide_border_strip_px"><input id="fullslide_border_strip_px" type="number" min="2" step="1" v-model="f.FULLSLIDE_BORDER_STRIP_PX" /></SettingsRow>
          <SettingsRow label="FULLSLIDE_MIN_MATCHED_SIDES" field-id="fullslide_min_matched_sides"><input id="fullslide_min_matched_sides" type="number" min="1" max="4" step="1" v-model="f.FULLSLIDE_MIN_MATCHED_SIDES" /></SettingsRow>
          <SettingsRow label="FULLSLIDE_BORDER_DIFF_THRESHOLD" field-id="fullslide_border_diff_threshold"><input id="fullslide_border_diff_threshold" type="number" min="0" step="0.1" v-model="f.FULLSLIDE_BORDER_DIFF_THRESHOLD" /></SettingsRow>
          <SettingsRow label="FULLSLIDE_PERSON_BOX_AREA_RATIO" field-id="fullslide_person_box_area_ratio"><input id="fullslide_person_box_area_ratio" type="number" min="0" max="1" step="0.01" v-model="f.FULLSLIDE_PERSON_BOX_AREA_RATIO" /></SettingsRow>
          <SettingsRow label="FULLSLIDE_PERSON_OUTSIDE_RATIO" field-id="fullslide_person_outside_ratio"><input id="fullslide_person_outside_ratio" type="number" min="0" max="1" step="0.01" v-model="f.FULLSLIDE_PERSON_OUTSIDE_RATIO" /></SettingsRow>
        </div>
      </StepSection>

      <!-- 6. Slide Edit -->
      <StepSection title="Slide Edit" subtitle="Cleans up the final slide set after speaker filtering." v-model:enabled="f.RUN_STEP_EDIT" v-model:expanded="expanded.edit" @update:enabled="onFieldStateChange">
        <div class="settings-list">
          <SettingsRow label="FINAL_SLIDE_POSTPROCESS_MODE" field-id="final_slide_postprocess_mode">
            <select id="final_slide_postprocess_mode" v-model="f.FINAL_SLIDE_POSTPROCESS_MODE" :disabled="!f.RUN_STEP_EDIT">
              <option value="local">local</option>
              <option value="gemini">nano banana</option>
              <option value="none">none</option>
            </select>
          </SettingsRow>
          <SettingsRow label="SLIDE_EDIT_REVIEW_RETRIES" field-id="gemini_edit_review_retries"><input id="gemini_edit_review_retries" type="number" min="0" max="5" step="1" v-model="f.GEMINI_EDIT_REVIEW_RETRIES" :disabled="!f.RUN_STEP_EDIT" /></SettingsRow>
          <SettingsRow label="SLIDE_EDIT_MODEL" field-id="gemini_edit_model">
            <select id="gemini_edit_model" v-model="f.GEMINI_EDIT_MODEL" :disabled="!f.RUN_STEP_EDIT">
              <option value="gemini-3.1-flash-image-preview">gemini-3.1-flash-image-preview</option>
              <option value="gemini-3-pro-image-preview">gemini-3-pro-image-preview</option>
              <option value="gemini-2.5-flash-image">gemini-2.5-flash-image</option>
            </select>
          </SettingsRow>
          <div class="settings-row settings-row-textarea">
            <label class="settings-key" for="gemini_edit_prompt">SLIDE_EDIT_PROMPT</label>
            <div class="settings-value"><textarea id="gemini_edit_prompt" rows="10" v-model="f.GEMINI_EDIT_PROMPT" :disabled="!f.RUN_STEP_EDIT"></textarea></div>
          </div>
        </div>
      </StepSection>

      <!-- 7. Slide Translate -->
      <StepSection title="Slide Translate" subtitle="Translates the final slide images via nano banana or Google OCR + Glossary rendering." v-model:enabled="f.RUN_STEP_TRANSLATE" v-model:expanded="expanded.translate" @update:enabled="onFieldStateChange">
        <div class="settings-list">
          <SettingsRow label="FINAL_SLIDE_TRANSLATION_MODE" field-id="final_slide_translation_mode">
            <select id="final_slide_translation_mode" v-model="f.FINAL_SLIDE_TRANSLATION_MODE" :disabled="!f.RUN_STEP_TRANSLATE" @change="onFieldStateChange">
              <option value="none">none</option>
              <option value="gemini">nano banana</option>
              <option value="deterministic_glossary">Google OCR + Glossary</option>
            </select>
          </SettingsRow>
          <!-- Gemini subsections -->
          <div class="settings-subsection">
            <h4 class="settings-subsection-head">Step 1 — Extract</h4>
            <div class="settings-list">
              <SettingsRow label="EXTRACT_MODEL" field-id="gemini_extract_model">
                <select id="gemini_extract_model" v-model="f.GEMINI_EXTRACT_MODEL" :disabled="!f.RUN_STEP_TRANSLATE || !geminiSlideTranslate">
                  <option value="gemini-3.1-pro-preview">gemini-3.1-pro-preview</option>
                  <option value="gemini-2.5-pro">gemini-2.5-pro</option>
                  <option value="gemini-2.5-flash">gemini-2.5-flash</option>
                </select>
              </SettingsRow>
              <div class="settings-row settings-row-textarea">
                <label class="settings-key" for="gemini_slide_extract_prompt">EXTRACT_PROMPT</label>
                <div class="settings-value"><textarea id="gemini_slide_extract_prompt" rows="5" v-model="f.GEMINI_SLIDE_EXTRACT_PROMPT" :disabled="!f.RUN_STEP_TRANSLATE || !geminiSlideTranslate"></textarea></div>
              </div>
            </div>
          </div>
          <div class="settings-subsection">
            <h4 class="settings-subsection-head">Step 2 — Translate</h4>
            <div class="settings-list">
              <div class="settings-row settings-row-textarea">
                <label class="settings-key" for="gemini_slide_translate_prompt">TRANSLATE_PROMPT</label>
                <div class="settings-value"><textarea id="gemini_slide_translate_prompt" rows="5" v-model="f.GEMINI_SLIDE_TRANSLATE_PROMPT" :disabled="!f.RUN_STEP_TRANSLATE || !geminiSlideTranslate"></textarea></div>
              </div>
            </div>
          </div>
          <div class="settings-subsection">
            <h4 class="settings-subsection-head">Step 3 — Render</h4>
            <div class="settings-list">
              <SettingsRow label="RENDER_MODEL" field-id="gemini_translate_model">
                <select id="gemini_translate_model" v-model="f.GEMINI_TRANSLATE_MODEL" :disabled="!f.RUN_STEP_TRANSLATE || !geminiSlideTranslate">
                  <option value="gemini-3.1-flash-image-preview">gemini-3.1-flash-image-preview</option>
                  <option value="gemini-3-pro-image-preview">gemini-3-pro-image-preview</option>
                  <option value="gemini-2.5-flash-image">gemini-2.5-flash-image</option>
                </select>
              </SettingsRow>
              <div class="settings-row settings-row-textarea">
                <label class="settings-key" for="gemini_slide_render_prompt">RENDER_PROMPT</label>
                <div class="settings-value"><textarea id="gemini_slide_render_prompt" rows="5" v-model="f.GEMINI_SLIDE_RENDER_PROMPT" :disabled="!f.RUN_STEP_TRANSLATE || !geminiSlideTranslate"></textarea></div>
              </div>
            </div>
          </div>
          <!-- Deterministic Glossary -->
          <div class="settings-subsection">
            <h4 class="settings-subsection-head">Deterministic Glossary</h4>
            <div class="settings-list">
              <SettingsRow label="SLIDE_TRANSLATE_MAX_FONT_SIZE" field-id="slide_translate_max_font_size"><input id="slide_translate_max_font_size" type="number" min="8" step="1" v-model="f.SLIDE_TRANSLATE_MAX_FONT_SIZE" :disabled="!f.RUN_STEP_TRANSLATE || !deterministicSlideTranslate" /></SettingsRow>
            </div>
          </div>
          <div class="settings-row termbase-settings-row">
            <label class="settings-key" for="slide_translate_styles_json">Slide Translate Styling</label>
            <div class="settings-value">
              <StyleEditor v-model="f.SLIDE_TRANSLATE_STYLES_JSON" :disabled="!f.RUN_STEP_TRANSLATE || !deterministicSlideTranslate" />
            </div>
          </div>
        </div>
      </StepSection>

      <!-- 8. Slide Upscale -->
      <StepSection title="Slide Upscale" subtitle="Upscales the final slide set locally or via Replicate to x4." v-model:enabled="f.RUN_STEP_UPSCALE" v-model:expanded="expanded.upscale" @update:enabled="onFieldStateChange">
        <div class="settings-list">
          <SettingsRow label="FINAL_SLIDE_UPSCALE_MODE" field-id="final_slide_upscale_mode">
            <select id="final_slide_upscale_mode" v-model="f.FINAL_SLIDE_UPSCALE_MODE" :disabled="!f.RUN_STEP_UPSCALE" @change="onFieldStateChange">
              <option value="none">none</option>
              <option value="swin2sr">swin2sr</option>
              <option value="replicate_nightmare_realesrgan">replicate_nightmare_realesrgan</option>
            </select>
          </SettingsRow>
          <SettingsRow label="FINAL_SLIDE_UPSCALE_MODEL" field-id="final_slide_upscale_model">
            <select id="final_slide_upscale_model" v-model="f.FINAL_SLIDE_UPSCALE_MODEL" :disabled="!f.RUN_STEP_UPSCALE || !localUpscale">
              <option value="caidas/swin2SR-classical-sr-x4-64">caidas/swin2SR-classical-sr-x4-64</option>
            </select>
          </SettingsRow>
          <SettingsRow label="FINAL_SLIDE_UPSCALE_DEVICE" field-id="final_slide_upscale_device">
            <select id="final_slide_upscale_device" v-model="f.FINAL_SLIDE_UPSCALE_DEVICE" :disabled="!f.RUN_STEP_UPSCALE || !localUpscale">
              <option value="auto">auto</option>
              <option value="cuda">cuda</option>
              <option value="cpu">cpu</option>
            </select>
          </SettingsRow>
          <SettingsRow label="FINAL_SLIDE_UPSCALE_TILE_SIZE" field-id="final_slide_upscale_tile_size"><input id="final_slide_upscale_tile_size" type="number" min="0" step="1" v-model="f.FINAL_SLIDE_UPSCALE_TILE_SIZE" :disabled="!f.RUN_STEP_UPSCALE || !localUpscale" /></SettingsRow>
          <SettingsRow label="FINAL_SLIDE_UPSCALE_TILE_OVERLAP" field-id="final_slide_upscale_tile_overlap"><input id="final_slide_upscale_tile_overlap" type="number" min="0" step="1" v-model="f.FINAL_SLIDE_UPSCALE_TILE_OVERLAP" :disabled="!f.RUN_STEP_UPSCALE || !localUpscale" /></SettingsRow>
          <SettingsRow label="REPLICATE_NIGHTMARE_REALESRGAN_MODEL_REF" field-id="replicate_nightmare_realesrgan_model_ref"><input id="replicate_nightmare_realesrgan_model_ref" type="text" v-model="f.REPLICATE_NIGHTMARE_REALESRGAN_MODEL_REF" :disabled="!f.RUN_STEP_UPSCALE || !replicateUpscale" /></SettingsRow>
          <SettingsRow label="REPLICATE_NIGHTMARE_REALESRGAN_VERSION_ID" field-id="replicate_nightmare_realesrgan_version_id"><input id="replicate_nightmare_realesrgan_version_id" type="text" v-model="f.REPLICATE_NIGHTMARE_REALESRGAN_VERSION_ID" :disabled="!f.RUN_STEP_UPSCALE || !replicateUpscale" /></SettingsRow>
          <SettingsRow label="REPLICATE_NIGHTMARE_REALESRGAN_PRICE_PER_SECOND" field-id="replicate_nightmare_realesrgan_price_per_second"><input id="replicate_nightmare_realesrgan_price_per_second" type="number" min="0" step="0.0001" v-model="f.REPLICATE_NIGHTMARE_REALESRGAN_PRICE_PER_SECOND" :disabled="!f.RUN_STEP_UPSCALE || !replicateUpscale" /></SettingsRow>
          <SettingsRow label="REPLICATE_UPSCALE_CONCURRENCY" field-id="replicate_upscale_concurrency"><input id="replicate_upscale_concurrency" type="number" min="1" step="1" v-model="f.REPLICATE_UPSCALE_CONCURRENCY" :disabled="!f.RUN_STEP_UPSCALE || f.FINAL_SLIDE_UPSCALE_MODE === 'none'" /></SettingsRow>
        </div>
      </StepSection>

      <!-- 9. TTS -->
      <StepSection title="TTS" subtitle="Generates a continuous transcript voiceover and aligns it back to the slides." v-model:enabled="f.RUN_STEP_TTS" v-model:expanded="expanded.tts" @update:enabled="onFieldStateChange">
        <div class="settings-list">
          <SettingsRow label="TTS_OUTPUT_LANGUAGE_CODE" field-id="google_tts_language_code">
            <input id="google_tts_language_code" type="text" readonly :value="f.GOOGLE_TTS_LANGUAGE_CODE" />
            <div class="tts-language-hint muted" :class="ttsHintClass" aria-live="polite">{{ ttsHintText }}</div>
          </SettingsRow>
          <SettingsRow label="TTS_MODEL" field-id="gemini_tts_model">
            <select id="gemini_tts_model" v-model="f.GEMINI_TTS_MODEL" :disabled="!f.RUN_STEP_TTS">
              <option value="gemini-2.5-flash-tts">gemini-2.5-flash-tts</option>
              <option value="gemini-2.5-pro-tts">gemini-2.5-pro-tts</option>
            </select>
          </SettingsRow>
          <SettingsRow label="GEMINI_TTS_VOICE" field-id="gemini_tts_voice"><input id="gemini_tts_voice" type="text" v-model="f.GEMINI_TTS_VOICE" :disabled="!f.RUN_STEP_TTS" /></SettingsRow>
          <SettingsRow label="GEMINI_TTS_SPEAKING_RATE" field-id="gemini_tts_speaking_rate"><input id="gemini_tts_speaking_rate" type="number" min="0.25" max="4.0" step="0.05" v-model="f.GEMINI_TTS_SPEAKING_RATE" :disabled="!f.RUN_STEP_TTS" /></SettingsRow>
          <div class="settings-row settings-row-textarea">
            <label class="settings-key" for="gemini_tts_prompt">TTS_PROMPT</label>
            <div class="settings-value"><textarea id="gemini_tts_prompt" rows="8" v-model="f.GEMINI_TTS_PROMPT" :disabled="!f.RUN_STEP_TTS"></textarea></div>
          </div>
        </div>
      </StepSection>

      <!-- 10. Video Export -->
      <StepSection title="Video Export" subtitle="Builds a new MP4 with SRT and timeline from the final slides and voiceover." v-model:enabled="f.RUN_STEP_VIDEO_EXPORT" v-model:expanded="expanded.videoExport" @update:enabled="onFieldStateChange">
        <div class="settings-list">
          <SettingsRow label="VIDEO_EXPORT_MIN_SLIDE_SEC" field-id="video_export_min_slide_sec"><input id="video_export_min_slide_sec" type="number" min="0.1" step="0.1" v-model="f.VIDEO_EXPORT_MIN_SLIDE_SEC" :disabled="!f.RUN_STEP_VIDEO_EXPORT" /></SettingsRow>
          <SettingsRow label="VIDEO_EXPORT_TAIL_PAD_SEC" field-id="video_export_tail_pad_sec"><input id="video_export_tail_pad_sec" type="number" min="0" step="0.05" v-model="f.VIDEO_EXPORT_TAIL_PAD_SEC" :disabled="!f.RUN_STEP_VIDEO_EXPORT" /></SettingsRow>
          <SettingsRow label="VIDEO_EXPORT_INTRO_WHITE_SEC" field-id="video_export_intro_white_sec"><input id="video_export_intro_white_sec" type="number" min="0" step="0.05" v-model="f.VIDEO_EXPORT_INTRO_WHITE_SEC" :disabled="!f.RUN_STEP_VIDEO_EXPORT" /></SettingsRow>
          <SettingsRow label="VIDEO_EXPORT_INTRO_FADE_SEC" field-id="video_export_intro_fade_sec"><input id="video_export_intro_fade_sec" type="number" min="0" step="0.05" v-model="f.VIDEO_EXPORT_INTRO_FADE_SEC" :disabled="!f.RUN_STEP_VIDEO_EXPORT" /></SettingsRow>
          <SettingsRow label="VIDEO_EXPORT_THUMBNAIL_DURATION_SEC" field-id="video_export_thumbnail_duration_sec"><input id="video_export_thumbnail_duration_sec" type="number" min="0.04" step="0.05" v-model="f.VIDEO_EXPORT_THUMBNAIL_DURATION_SEC" :disabled="!f.RUN_STEP_VIDEO_EXPORT" /></SettingsRow>
          <SettingsRow label="VIDEO_EXPORT_THUMBNAIL_FADE_SEC" field-id="video_export_thumbnail_fade_sec"><input id="video_export_thumbnail_fade_sec" type="number" min="0" step="0.05" v-model="f.VIDEO_EXPORT_THUMBNAIL_FADE_SEC" :disabled="!f.RUN_STEP_VIDEO_EXPORT" /></SettingsRow>
          <SettingsRow label="VIDEO_EXPORT_THUMBNAIL_TEXT_LEADIN_SEC" field-id="video_export_thumbnail_text_leadin_sec"><input id="video_export_thumbnail_text_leadin_sec" type="number" min="0" step="0.05" v-model="f.VIDEO_EXPORT_THUMBNAIL_TEXT_LEADIN_SEC" :disabled="!f.RUN_STEP_VIDEO_EXPORT" /></SettingsRow>
          <SettingsRow label="VIDEO_EXPORT_INTRO_COLOR" field-id="video_export_intro_color"><input id="video_export_intro_color" type="text" v-model="f.VIDEO_EXPORT_INTRO_COLOR" :disabled="!f.RUN_STEP_VIDEO_EXPORT" /></SettingsRow>
          <SettingsRow label="VIDEO_EXPORT_OUTRO_HOLD_SEC" field-id="video_export_outro_hold_sec"><input id="video_export_outro_hold_sec" type="number" min="0" step="0.05" v-model="f.VIDEO_EXPORT_OUTRO_HOLD_SEC" :disabled="!f.RUN_STEP_VIDEO_EXPORT" /></SettingsRow>
          <SettingsRow label="VIDEO_EXPORT_OUTRO_FADE_SEC" field-id="video_export_outro_fade_sec"><input id="video_export_outro_fade_sec" type="number" min="0" step="0.05" v-model="f.VIDEO_EXPORT_OUTRO_FADE_SEC" :disabled="!f.RUN_STEP_VIDEO_EXPORT" /></SettingsRow>
          <SettingsRow label="VIDEO_EXPORT_OUTRO_FADE_COLOR" field-id="video_export_outro_fade_color"><input id="video_export_outro_fade_color" type="text" v-model="f.VIDEO_EXPORT_OUTRO_FADE_COLOR" :disabled="!f.RUN_STEP_VIDEO_EXPORT" /></SettingsRow>
          <SettingsRow label="VIDEO_EXPORT_OUTRO_BLACK_SEC" field-id="video_export_outro_black_sec"><input id="video_export_outro_black_sec" type="number" min="0" step="0.05" v-model="f.VIDEO_EXPORT_OUTRO_BLACK_SEC" :disabled="!f.RUN_STEP_VIDEO_EXPORT" /></SettingsRow>
          <SettingsRow label="VIDEO_EXPORT_WIDTH" field-id="video_export_width"><input id="video_export_width" type="number" min="2" step="2" v-model="f.VIDEO_EXPORT_WIDTH" :disabled="!f.RUN_STEP_VIDEO_EXPORT" /></SettingsRow>
          <SettingsRow label="VIDEO_EXPORT_HEIGHT" field-id="video_export_height"><input id="video_export_height" type="number" min="2" step="2" v-model="f.VIDEO_EXPORT_HEIGHT" :disabled="!f.RUN_STEP_VIDEO_EXPORT" /></SettingsRow>
          <SettingsRow label="VIDEO_EXPORT_FPS" field-id="video_export_fps"><input id="video_export_fps" type="number" min="1" step="1" v-model="f.VIDEO_EXPORT_FPS" :disabled="!f.RUN_STEP_VIDEO_EXPORT" /></SettingsRow>
          <SettingsRow label="VIDEO_EXPORT_BG_COLOR" field-id="video_export_bg_color"><input id="video_export_bg_color" type="text" v-model="f.VIDEO_EXPORT_BG_COLOR" :disabled="!f.RUN_STEP_VIDEO_EXPORT" /></SettingsRow>
        </div>
      </StepSection>

      <!-- 11. Backup -->
      <StepSection title="Backup" subtitle="Uploads all output files from the current run to a Google Drive folder." v-model:enabled="f.RUN_STEP_BACKUP" v-model:expanded="expanded.backup" @update:enabled="onFieldStateChange">
        <div class="settings-list">
          <div class="settings-row">
            <label class="settings-key">Google Drive Auth</label>
            <div class="settings-value gdrive-auth-row">
              <span v-if="gdriveLoading" class="gdrive-auth-label is-loading"><span class="auth-spinner"></span> Checking...</span>
              <span v-else-if="gdriveStatus.authenticated" class="gdrive-auth-label is-ok">{{ gdriveStatus.email }}</span>
              <span v-else class="gdrive-auth-label is-warning">Not authenticated</span>
              <a href="/api/gdrive/auth/start" class="btn-sm">
                {{ gdriveStatus.authenticated ? 'Re-authenticate' : 'Authenticate' }}
              </a>
            </div>
          </div>
          <SettingsRow label="GDRIVE_FOLDER_ID" field-id="gdrive_folder_id"><input id="gdrive_folder_id" type="text" placeholder="Google Drive folder ID" v-model="f.GDRIVE_FOLDER_ID" :disabled="!f.RUN_STEP_BACKUP" /></SettingsRow>
        </div>
      </StepSection>

      <!-- 12. Test APIs (forced) -->
      <StepSection title="Test APIs" subtitle="Test each pipeline API endpoint individually." :forced="true" v-model:expanded="expanded.testApis">
        <div class="settings-list">
          <SettingsRow label="GCLOUD_PROJECT_ID" field-id="gcloud_project_id"><input id="gcloud_project_id" type="text" placeholder="Google Cloud project id" v-model="f.GCLOUD_PROJECT_ID" /></SettingsRow>
        </div>
        <div id="health-app"></div>
      </StepSection>
    </div>
  </section>
</template>

<script setup>
import { reactive, ref, computed, watch, onMounted } from "vue";
import { configStore as store, findTtsLanguageOptionByCode } from "../stores/configStore.js";
import StepSection from "../components/StepSection.vue";
import SettingsRow from "../components/SettingsRow.vue";
import TtsLanguageSelector from "../components/TtsLanguageSelector.vue";
import TermbaseEditor from "../components/TermbaseEditor.vue";
import StyleEditor from "../components/StyleEditor.vue";

const f = store.form;

const EXPANDED_KEY = "settings-expanded";
const defaultExpanded = {
  slideDetection: false,
  transcription: false,
  textTranslate: false,
  transcriptMapping: false,
  finalizeSlides: false,
  edit: false,
  translate: false,
  upscale: false,
  tts: false,
  videoExport: false,
  backup: false,
  testApis: false,
};
function loadExpanded() {
  try {
    const saved = JSON.parse(localStorage.getItem(EXPANDED_KEY));
    if (saved && typeof saved === "object") return { ...defaultExpanded, ...saved };
  } catch { /* ignore */ }
  return { ...defaultExpanded };
}
const expanded = reactive(loadExpanded());
watch(() => ({ ...expanded }), (val) => {
  localStorage.setItem(EXPANDED_KEY, JSON.stringify(val));
});

const googleTranscription = computed(() => f.TRANSCRIPTION_PROVIDER === "google_chirp_3");
const geminiSlideTranslate = computed(() => f.FINAL_SLIDE_TRANSLATION_MODE === "gemini");
const deterministicSlideTranslate = computed(() => f.FINAL_SLIDE_TRANSLATION_MODE === "deterministic_glossary");
const localUpscale = computed(() => f.FINAL_SLIDE_UPSCALE_MODE === "swin2sr");
const replicateUpscale = computed(() => f.FINAL_SLIDE_UPSCALE_MODE === "replicate_nightmare_realesrgan");

const textTranslateUsesGeminiApi = computed(() => String(f.TRANSCRIPT_TRANSLATE_MODEL || "").trim().toLowerCase().startsWith("gemini-"));
const cloudTranslateConfigEnabled = computed(() =>
  (f.RUN_STEP_TEXT_TRANSLATE && !textTranslateUsesGeminiApi.value) || (f.RUN_STEP_TRANSLATE && deterministicSlideTranslate.value));
const sourceLanguageConfigEnabled = computed(() => f.RUN_STEP_TEXT_TRANSLATE || (f.RUN_STEP_TRANSLATE && deterministicSlideTranslate.value));
const languageSelectionEnabled = computed(() => f.RUN_STEP_TRANSLATE || f.RUN_STEP_TEXT_TRANSLATE || f.RUN_STEP_TTS || googleTranscription.value);

// TTS language hint
const selectedTtsOption = computed(() => findTtsLanguageOptionByCode(f.GOOGLE_TTS_LANGUAGE_CODE));
const ttsHintText = computed(() => {
  if (!f.RUN_STEP_TTS) return "";
  const selected = selectedTtsOption.value;
  if (!selected) return "Select a supported Gemini TTS language from the catalog.";
  if (!f.RUN_STEP_TEXT_TRANSLATE) {
    return `TTS will use ${selected.label} [${selected.tts_language_code}] for the source mapped text because Transcript Translate is disabled.`;
  }
  const readiness = selected.launch_readiness ? ` | ${selected.launch_readiness}` : "";
  return `Selected Gemini TTS language: ${selected.label} | ${selected.tts_language_code}${readiness}`;
});
const ttsHintClass = computed(() => {
  if (!f.RUN_STEP_TTS) return "is-idle";
  if (!selectedTtsOption.value) return "is-warning";
  if (!f.RUN_STEP_TEXT_TRANSLATE) return "is-note";
  return "is-ok";
});

function onTtsLanguageChange(code) {
  f.GOOGLE_TTS_LANGUAGE_CODE = code;
  const opt = findTtsLanguageOptionByCode(code);
  if (opt) f.FINAL_SLIDE_TARGET_LANGUAGE = opt.label;
}

function onFieldStateChange() {
  document.dispatchEvent(new CustomEvent("health-stt-sync", { detail: { googleTranscription: googleTranscription.value } }));
}

// Google Cloud ADC auth (for Gemini, TTS, Vision, etc.)
const gcloudStatus = ref({ configured: false, email: "" });
const gcloudLoading = ref(true);

async function fetchGcloudStatus() {
  gcloudLoading.value = true;
  try {
    const res = await fetch("/api/gcloud/status");
    if (res.ok) gcloudStatus.value = await res.json();
  } catch { /* ignore */ }
  gcloudLoading.value = false;
}

// Google Drive auth (separate, for Backup step)
const gdriveStatus = ref({ authenticated: false, email: "" });
const gdriveLoading = ref(true);

async function fetchGdriveStatus() {
  gdriveLoading.value = true;
  try {
    const res = await fetch("/api/gdrive/status");
    if (res.ok) gdriveStatus.value = await res.json();
  } catch { /* ignore */ }
  gdriveLoading.value = false;
}

const authResultMsg = ref("");
const authResultOk = ref(false);

onMounted(() => {
  fetchGcloudStatus();
  fetchGdriveStatus();
  const params = new URLSearchParams(location.search);
  if (params.has("gcloud_auth")) {
    const ok = params.get("gcloud_auth") === "done";
    authResultMsg.value = ok ? "Google Cloud auth: done" : "Google Cloud auth: failed";
    authResultOk.value = ok;
    history.replaceState(null, "", location.pathname);
  } else if (params.has("gdrive_auth")) {
    const ok = params.get("gdrive_auth") === "done";
    authResultMsg.value = ok ? "Google Drive auth: done" : "Google Drive auth: failed";
    authResultOk.value = ok;
    history.replaceState(null, "", location.pathname);
  }
});

watch(googleTranscription, () => {
  onFieldStateChange();
});
</script>
