<template>
  <div>
    <div class="settings-list">
      <SettingsRow label="GCLOUD_PROJECT_ID" field-id="gcloud_project_id"><input id="gcloud_project_id" type="text" placeholder="Google Cloud project id" v-model="f.GCLOUD_PROJECT_ID" /></SettingsRow>
    </div>
    <div id="health-app"></div>
  </div>
</template>

<script setup>
import { configStore as store } from "../../stores/configStore.js";
import SettingsRow from "../../components/SettingsRow.vue";

const f = store.form;
</script>
