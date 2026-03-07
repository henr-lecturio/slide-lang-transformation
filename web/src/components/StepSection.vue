<template>
  <section
    class="step-section"
    :class="{
      'is-forced': forced,
      'is-enabled': enabled,
      'is-disabled': !enabled,
      'is-open': showBody,
    }"
  >
    <div class="step-section-head">
      <div class="step-section-title-wrap">
        <div v-if="forced" class="step-section-note muted">This pipeline step always runs.</div>
        <div class="step-section-heading">
          <label v-if="forced" class="step-switch is-static step-switch-icononly">
            <input type="checkbox" checked disabled :aria-label="`${title} is always enabled`" />
          </label>
          <label v-else class="step-switch step-switch-icononly">
            <input
              type="checkbox"
              :checked="enabled"
              :aria-label="`Enable ${title}`"
              @change="$emit('update:enabled', $event.target.checked)"
            />
          </label>
          <h3>{{ title }}</h3>
          <button
            type="button"
            class="step-section-toggle"
            :disabled="!forced && !enabled"
            :aria-expanded="showBody ? 'true' : 'false'"
            :aria-label="`Toggle ${title} settings`"
            @click="toggle"
          >
            <span class="step-section-chevron" aria-hidden="true"></span>
          </button>
        </div>
        <div v-if="subtitle" class="step-section-subtitle muted">{{ subtitle }}</div>
      </div>
    </div>
    <div class="step-section-body" :hidden="!showBody" :aria-hidden="showBody ? 'false' : 'true'">
      <slot />
    </div>
  </section>
</template>

<script setup>
import { computed } from "vue";

const props = defineProps({
  title: { type: String, required: true },
  subtitle: { type: String, default: "" },
  forced: { type: Boolean, default: false },
  enabled: { type: Boolean, default: true },
  expanded: { type: Boolean, default: false },
});

const emit = defineEmits(["update:expanded", "update:enabled"]);

const showBody = computed(() => {
  if (props.forced) return props.expanded;
  return props.enabled && props.expanded;
});

function toggle() {
  if (!props.forced && !props.enabled) return;
  emit("update:expanded", !props.expanded);
}
</script>
