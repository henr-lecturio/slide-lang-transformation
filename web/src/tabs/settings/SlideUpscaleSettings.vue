<template>
  <div class="settings-list">
    <SettingsRow label="FINAL_SLIDE_UPSCALE_MODE" field-id="final_slide_upscale_mode">
      <select id="final_slide_upscale_mode" v-model="f.FINAL_SLIDE_UPSCALE_MODE" :disabled="!f.RUN_STEP_UPSCALE" @change="$emit('field-change')">
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
</template>

<script setup>
import { computed } from "vue";
import { configStore as store } from "../../stores/configStore.js";
import SettingsRow from "../../components/SettingsRow.vue";

defineEmits(["field-change"]);

const f = store.form;
const localUpscale = computed(() => f.FINAL_SLIDE_UPSCALE_MODE === "swin2sr");
const replicateUpscale = computed(() => f.FINAL_SLIDE_UPSCALE_MODE === "replicate_nightmare_realesrgan");
</script>
