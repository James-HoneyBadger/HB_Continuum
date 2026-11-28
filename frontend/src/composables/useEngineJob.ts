import { onUnmounted, ref } from "vue";
import { invoke } from "@tauri-apps/api/core";
import { listen, type UnlistenFn } from "@tauri-apps/api/event";

export interface JobOutcome {
  event: "job_complete" | "job_error";
  result?: any;
  code?: string;
  message?: string;
}

/**
 * Start engine background jobs and resolve when they finish.
 *
 * The Rust bridge forwards engine event lines as `engine-event`; events for a
 * job can arrive before the start response is processed, so recent events are
 * replayed once the job id is known.
 */
export function useEngineJob() {
  const busy = ref(false);
  const progress = ref("");

  let activeJob = "";
  let terminal: JobOutcome | null = null;
  let waiter: ((outcome: JobOutcome) => void) | null = null;
  const recent: any[] = [];
  let unlisten: UnlistenFn | null = null;

  function apply(payload: any) {
    if (!activeJob || payload.job_id !== activeJob) return;
    if (payload.event === "progress") {
      progress.value = `${payload.done}/${payload.total} ${payload.status}`;
      return;
    }
    if (payload.event !== "job_complete" && payload.event !== "job_error") return;
    if (terminal) return;
    terminal = {
      event: payload.event,
      result: payload.result,
      code: payload.code,
      message: payload.message,
    };
    busy.value = false;
    if (waiter) {
      const resolve = waiter;
      waiter = null;
      resolve(terminal);
    }
  }

  function handle(payload: any) {
    recent.push(payload);
    if (recent.length > 50) recent.shift();
    apply(payload);
  }

  async function ensureListener() {
    if (!unlisten) unlisten = await listen("engine-event", (event) => handle(event.payload));
  }

  async function cancel() {
    if (!activeJob) return;
    try {
      await invoke("cancel", { jobId: activeJob });
    } catch {
      // The job may already have finished; nothing else to do.
    }
  }

  async function start(method: string, params: Record<string, unknown> = {}): Promise<JobOutcome> {
    if (busy.value) throw new Error("another operation is already running");
    await ensureListener();
    busy.value = true;
    progress.value = "starting…";
    let jobId: string;
    try {
      const response = (await invoke(method, params)) as { job_id: string };
      jobId = response.job_id;
    } catch (e) {
      busy.value = false;
      progress.value = "";
      throw e;
    }
    activeJob = jobId;
    terminal = null;
    for (const payload of recent) apply(payload);
    if (terminal) return terminal;
    return new Promise<JobOutcome>((resolve) => {
      waiter = resolve;
    });
  }

  onUnmounted(() => {
    if (unlisten) unlisten();
  });

  return { busy, progress, start, cancel };
}
