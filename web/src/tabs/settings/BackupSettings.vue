<template>
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
</template>

<script setup>
import { configStore as store } from "../../stores/configStore.js";
import SettingsRow from "../../components/SettingsRow.vue";

defineProps({
  gdriveStatus: { type: Object, default: () => ({ authenticated: false, email: "" }) },
  gdriveLoading: { type: Boolean, default: false },
});

const f = store.form;
</script>
