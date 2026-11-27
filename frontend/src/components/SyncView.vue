<script setup lang="ts">
import { ref } from "vue";
import { invoke } from "@tauri-apps/api/core";

const props = defineProps<{ onError: (message: string) => void; onChanged: () => void }>();

const profiles = ref<Record<string, any>>({});
const status = ref<Record<string, any>>({});
const notice = ref("");
const jobState = ref("");
const draft = ref({
  name: "",
  host: "",
  user: "",
  folders: "INBOX",
  mode: "Interval",
  time: "30",
  enabled: false,
});

async function refresh() {
  try {
    const response = (await invoke("schedule_status")) as {
      profiles: Record<string, any>;
      status: Record<string, any>;
    };
    profiles.value = response.profiles;
    status.value = response.status;
  } catch (e) {
    props.onError(String(e));
  }
}

async function saveProfile() {
  notice.value = "";
  const interval = draft.value.mode === "Interval";
  try {
    await invoke("schedule_profile_save", {
      name: draft.value.name.trim(),
      host: draft.value.host.trim(),
      user: draft.value.user.trim(),
      folders: draft.value.folders.split(";").map((f) => f.trim()).filter(Boolean),
      minutes: interval ? Number(draft.value.time) : null,
      daily: interval ? null : draft.value.time,
      enabled: draft.value.enabled,
    });
    notice.value = `Profile “${draft.value.name}” saved.`;
    await refresh();
    props.onChanged();
  } catch (e) {
    props.onError(String(e));
  }
}

async function toggle(name: string, enabled: boolean) {
  notice.value = "";
  try {
    await invoke("schedule_profile_enabled", { name, enabled: !enabled });
    await refresh();
  } catch (e) {
    props.onError(String(e));
  }
}

async function runNow(name: string) {
  notice.value = "";
  jobState.value = `Running ${name}…`;
  try {
    await invoke("schedule_run", { name });
    pollJob();
  } catch (e) {
    jobState.value = "";
    props.onError(String(e));
  }
}

function pollJob() {
  setTimeout(async () => {
    await refresh();
    const entry = Object.values(status.value)[0];
    if (entry && entry.status && !String(entry.status).startsWith("running")) {
      jobState.value = String(entry.status);
      props.onChanged();
    } else {
      pollJob();
    }
  }, 1500);
}

refresh();
</script>

<template>
  <section>
    <h2>Synchronization</h2>
    <p class="meta">
      Read-only IMAP retrieval. Passwords are never stored in profiles or transferred through this interface;
      the engine resolves credentials from the operating system credential store when a sync runs.
    </p>
    <p class="warn">
      Background scheduling and credential retrieval are currently implemented for macOS (Keychain +
      launchd). On Linux and Windows, running a profile reports an explicit credential error until the
      portable scheduler lands. Manual ad-hoc sync with a typed password remains a CLI operation
      (<code>dispatch sync</code>).
    </p>
    <p v-if="notice" class="notice">{{ notice }}</p>
    <p v-if="jobState" class="meta">{{ jobState }}</p>

    <h3>Profiles</h3>
    <ul class="plain">
      <li v-for="(profile, name) in profiles" :key="name">
        <strong>{{ name }}</strong>
        <span class="meta">{{ profile.user }} @ {{ profile.host }} · {{ profile.folders.join(", ") }}</span>
        <span class="meta">{{ profile.minutes ? "every " + profile.minutes + " min" : "daily " + profile.daily }}</span>
        <span class="meta">{{ (status[name] && status[name].status) || "not run" }}</span>
        <button @click="toggle(String(name), !!profile.enabled)">
          {{ profile.enabled ? "Disable" : "Enable" }}
        </button>
        <button @click="runNow(String(name))">Run now</button>
      </li>
    </ul>

    <h3>Add or update a profile</h3>
    <div class="row">
      <input v-model="draft.name" placeholder="Profile name" />
      <input v-model="draft.host" placeholder="IMAP host" />
      <input v-model="draft.user" placeholder="Username" />
    </div>
    <div class="row">
      <input v-model="draft.folders" placeholder="Folders (semicolon separated)" />
      <select v-model="draft.mode">
        <option>Interval</option>
        <option>Daily</option>
      </select>
      <input v-model="draft.time" placeholder="minutes or HH:MM" class="narrow" />
      <label class="inline"><input type="checkbox" v-model="draft.enabled" /> Enabled</label>
      <button @click="saveProfile">Save profile</button>
    </div>
  </section>
</template>

<style scoped>
.row {
  display: flex;
  gap: 8px;
  margin-bottom: 10px;
  align-items: center;
  flex-wrap: wrap;
}
input {
  padding: 6px;
  font-size: 13px;
  flex: 1;
  min-width: 130px;
}
.narrow {
  flex: 0 0 130px;
  min-width: 130px;
}
select {
  padding: 6px;
}
button {
  padding: 6px 14px;
  margin-left: 6px;
}
.plain {
  list-style: none;
  padding: 0;
}
.plain li {
  padding: 6px 0;
  border-bottom: 1px solid #eee;
  font-size: 13px;
}
.meta {
  color: #777;
  font-size: 12px;
  margin-left: 8px;
}
.warn {
  background: #fff8e1;
  border-left: 3px solid #d8a400;
  padding: 8px 12px;
  font-size: 13px;
  color: #4a3b00;
}
.notice {
  color: #2e6b2e;
}
.inline {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 13px;
}
.inline input {
  flex: 0 0 auto;
  min-width: 0;
}
</style>
