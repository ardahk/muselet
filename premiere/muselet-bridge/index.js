/*
 * Muselet Bridge — UXP panel plugin for Adobe Premiere Pro 26.x (macOS).  UNTESTED.
 *
 * UXP plugins cannot host servers ("UXP supports WebSocket clients only",
 * https://developer.adobe.com/premiere-pro/uxp/resources/recipes/network/), so the panel connects OUT to
 * the muselet brain at ws://127.0.0.1:8766 and executes one JSON command per frame:
 *   request  {"id": "...", "cmd": "<name>", "args": {...}}
 *   reply    {"id": "...", "ok": true, "result": {...}}  |  {"id": "...", "ok": false, "error": "..."}
 * Unsupported commands reply ok:false, error:"not_supported".
 *
 * API reference: https://developer.adobe.com/premiere-pro/uxp/ppro-reference/  (abbreviated "REF" below)
 * Since Premiere 26.3, every create*Action call must happen inside project.lockedAccess()
 * (REF changelog "Action creation in locks"); all edits below follow that pattern.
 */

const ppro = require("premierepro");

const BRAIN_URL = "ws://127.0.0.1:8766";
const RECONNECT_MIN_MS = 500;
const RECONNECT_MAX_MS = 10000;

let socket = null;
let reconnectMs = RECONNECT_MIN_MS;
let reconnectTimer = null;

function log(msg) {
  console.log(`[muselet] ${msg}`);
  const el = typeof document !== "undefined" && document.getElementById("log");
  if (el) {
    el.textContent = `${new Date().toLocaleTimeString()} ${msg}\n` + el.textContent.slice(0, 4000);
  }
}

function setStatus(text) {
  const el = typeof document !== "undefined" && document.getElementById("status");
  if (el) el.textContent = text;
}

class NotSupported extends Error {
  constructor(detail) {
    super("not_supported");
    this.detail = detail;
  }
}

// ---------- helpers ----------

// REF classes/project.md#getactiveproject, #getactivesequence
async function activeProjectAndSequence() {
  const project = await ppro.Project.getActiveProject();
  if (!project) throw new Error("no active project");
  const sequence = await project.getActiveSequence();
  if (!sequence) throw new Error("no active sequence");
  return { project, sequence };
}

// REF classes/project.md#lockedaccess, #executetransaction (returns boolean; undoable as one step)
function runTransaction(project, label, buildActions) {
  let ok = false;
  project.lockedAccess(() => {
    const actions = buildActions();
    ok = project.executeTransaction((compoundAction) => {
      for (const a of actions) compoundAction.addAction(a);
    }, label);
  });
  if (!ok) throw new Error(`transaction failed: ${label}`);
  return ok;
}

const seconds = (tickTime) => (tickTime && typeof tickTime.seconds === "number" ? tickTime.seconds : null);

// REF classes/videotrack.md#gettrackitems (sync, returns VideoClipTrackItem[]),
//     classes/audiotrack.md#gettrackitems, classes/videocliptrackitem.md#getname/#getstarttime/#getendtime
async function describeTracks(sequence, kind) {
  const count = kind === "video" ? await sequence.getVideoTrackCount() : await sequence.getAudioTrackCount();
  const tracks = [];
  for (let i = 0; i < count; i++) {
    const track = kind === "video" ? await sequence.getVideoTrack(i) : await sequence.getAudioTrack(i);
    if (!track) continue;
    const items = track.getTrackItems(ppro.Constants.TrackItemType.CLIP, false) || [];
    const clips = [];
    for (const item of items) {
      clips.push({
        name: await item.getName(),
        start: seconds(await item.getStartTime()),
        end: seconds(await item.getEndTime()),
      });
    }
    tracks.push({ index: i, name: track.name, clip_count: clips.length, clips });
  }
  return { count, tracks };
}

async function videoClipsOnTrack(sequence, trackIndex) {
  const track = await sequence.getVideoTrack(trackIndex);
  if (!track) throw new Error(`no video track ${trackIndex + 1}`);
  return track.getTrackItems(ppro.Constants.TrackItemType.CLIP, false) || [];
}

// ---------- commands ----------

const COMMANDS = {
  // REF classes/sequence.md: name, getEndTime, getPlayerPosition, getVideoTrackCount, getAudioTrackCount,
  //     getVideoTrack, getAudioTrack
  async sequence_info() {
    const { sequence } = await activeProjectAndSequence();
    const video = await describeTracks(sequence, "video");
    const audio = await describeTracks(sequence, "audio");
    return {
      name: sequence.name,
      duration: seconds(await sequence.getEndTime()),
      playhead: seconds(await sequence.getPlayerPosition()),
      video_track_count: video.count,
      audio_track_count: audio.count,
      video_clip_count: video.tracks.reduce((n, t) => n + t.clip_count, 0),
      audio_clip_count: audio.tracks.reduce((n, t) => n + t.clip_count, 0),
      video_tracks: video.tracks,
      audio_tracks: audio.tracks,
    };
  },

  // REF classes/markers.md#getmarkers (static, async) and #createaddmarkeraction(name, markerType, startTime,
  //     duration, comments); marker types "Comment" | "Chapter" | "Segmentation" | "WebLink" (classes/marker.md)
  async add_marker(args) {
    const { project, sequence } = await activeProjectAndSequence();
    const at = await sequence.getPlayerPosition();
    const markers = await ppro.Markers.getMarkers(sequence);
    const name = (args && args.name) || "Marker";
    const markerType = (ppro.Marker && ppro.Marker.MARKER_TYPE_COMMENT) || "Comment";
    runTransaction(project, "Muselet: add marker", () => [
      markers.createAddMarkerAction(name, markerType, at, ppro.TickTime.TIME_ZERO, (args && args.comments) || ""),
    ]);
    return { name, time: seconds(at) };
  },

  // No razor/split API is documented for Premiere 26.x UXP (checked REF classes/sequence.md,
  // sequenceeditor.md, sequenceutils.md, videocliptrackitem.md). The app can fall back to the Cmd+K shortcut.
  async razor_at_playhead() {
    throw new NotSupported("no razor/split API in Premiere UXP 26.x; use keyboard shortcut cmd+k");
  },

  // REF classes/transitionfactory.md#getvideotransitionmatchnames/#createvideotransition,
  //     classes/addtransitionoptions.md (constructor, setApplyToStart, setForceSingleSided, setDuration),
  //     classes/videocliptrackitem.md#createaddvideotransitionaction
  // args: {index: 0-based clip i on V1 (transition goes on the edit between clip i and i+1),
  //        match_name?: string, duration?: seconds}
  async add_transition(args) {
    args = args || {};
    const i = Number.isInteger(args.index) ? args.index : 0;
    const trackIndex = Number.isInteger(args.track) ? args.track : 0;
    const { project, sequence } = await activeProjectAndSequence();
    const clips = await videoClipsOnTrack(sequence, trackIndex);
    if (i < 0 || i + 1 >= clips.length) {
      throw new Error(`need clips ${i} and ${i + 1} on V${trackIndex + 1}; track has ${clips.length}`);
    }
    const names = (await ppro.TransitionFactory.getVideoTransitionMatchNames()) || [];
    if (!names.length) throw new Error("no video transitions available");
    const matchName = args.match_name || names.find((n) => /cross\s*dissolve/i.test(n)) || names[0];
    const transition = await ppro.TransitionFactory.createVideoTransition(matchName);
    const options = new ppro.AddTransitionOptions();
    options.setApplyToStart(false); // end of clip i == the cut into clip i+1
    options.setForceSingleSided(false);
    if (typeof args.duration === "number") options.setDuration(ppro.TickTime.createWithSeconds(args.duration));
    runTransaction(project, "Muselet: add transition", () => [
      clips[i].createAddVideoTransitionAction(transition, options),
    ]);
    return { match_name: matchName, between: [i, i + 1], track: trackIndex };
  },

  // REF classes/sequence.md#setplayerposition (Promise<boolean>), classes/ticktime.md#createwithseconds
  async move_playhead(args) {
    const s = Number(args && args.seconds);
    if (!Number.isFinite(s) || s < 0) throw new Error("args.seconds must be a non-negative number");
    const { sequence } = await activeProjectAndSequence();
    const ok = await sequence.setPlayerPosition(ppro.TickTime.createWithSeconds(s));
    if (!ok) throw new Error("setPlayerPosition returned false");
    return { playhead: seconds(await sequence.getPlayerPosition()) };
  },

  // REF classes/encodermanager.md#getmanager, #exportsequence(sequence, exportType, outputFile, presetFile,
  //     exportFull) -> Promise<boolean>; constants/index.md#exporttype (IMMEDIATELY | QUEUE_TO_AME | QUEUE_TO_APP)
  // args: {preset_path: ".epr", output_path: absolute file path, queue_to_ame?: bool, full?: bool}
  async export_sequence(args) {
    args = args || {};
    if (!args.preset_path || !args.output_path) throw new Error("args.preset_path and args.output_path are required");
    const { sequence } = await activeProjectAndSequence();
    const manager = ppro.EncoderManager.getManager();
    const exportType = args.queue_to_ame ? ppro.Constants.ExportType.QUEUE_TO_AME : ppro.Constants.ExportType.IMMEDIATELY;
    if (args.queue_to_ame && !manager.isAMEInstalled) throw new Error("Adobe Media Encoder is not installed");
    const ok = await manager.exportSequence(sequence, exportType, args.output_path, args.preset_path, args.full !== false);
    if (!ok) throw new Error("exportSequence returned false");
    return { output_path: args.output_path, queued: !!args.queue_to_ame };
  },

  // No undo API is documented (REF project.md only exposes executeTransaction(undoString) to create undo
  // steps). The app should send cmd+z to Premiere instead.
  async undo() {
    throw new NotSupported("no undo API in Premiere UXP 26.x; use keyboard shortcut cmd+z");
  },

  async ping() {
    return { pong: true, host: "premierepro" };
  },
};

// ---------- transport ----------

async function handle(raw) {
  let msg;
  try {
    msg = JSON.parse(raw);
  } catch (e) {
    return { id: null, ok: false, error: "invalid JSON" };
  }
  const id = msg && msg.id !== undefined ? msg.id : null;
  const fn = msg && Object.prototype.hasOwnProperty.call(COMMANDS, msg.cmd) ? COMMANDS[msg.cmd] : null;
  if (!fn) return { id, ok: false, error: `unknown command: ${msg && msg.cmd}` };
  try {
    const result = await fn(msg.args || {});
    return { id, ok: true, result };
  } catch (e) {
    if (e instanceof NotSupported) return { id, ok: false, error: "not_supported", detail: e.detail };
    return { id, ok: false, error: String((e && e.message) || e) };
  }
}

function scheduleReconnect() {
  if (reconnectTimer) return;
  setStatus(`disconnected, retry in ${Math.round(reconnectMs / 1000)}s`);
  reconnectTimer = setTimeout(() => {
    reconnectTimer = null;
    connect();
  }, reconnectMs);
  reconnectMs = Math.min(reconnectMs * 2, RECONNECT_MAX_MS);
}

function connect() {
  if (socket && (socket.readyState === 0 || socket.readyState === 1)) return;
  setStatus("connecting");
  try {
    socket = new WebSocket(BRAIN_URL);
  } catch (e) {
    log(`connect error: ${e}`);
    scheduleReconnect();
    return;
  }
  socket.onopen = () => {
    reconnectMs = RECONNECT_MIN_MS;
    setStatus("connected");
    log(`connected to ${BRAIN_URL}`);
    socket.send(JSON.stringify({ t: "hello", client: "premiere-bridge", version: "0.1.0", commands: Object.keys(COMMANDS) }));
  };
  socket.onmessage = async (event) => {
    const reply = await handle(event.data);
    log(`${reply.ok ? "ok " : "ERR"} ${reply.id} ${reply.ok ? "" : reply.error}`);
    if (socket && socket.readyState === 1) socket.send(JSON.stringify(reply));
  };
  socket.onerror = (e) => log(`socket error: ${(e && e.message) || e}`);
  socket.onclose = () => {
    socket = null;
    scheduleReconnect();
  };
}

if (typeof document !== "undefined") {
  const btn = document.getElementById("reconnect");
  if (btn) {
    btn.addEventListener("click", () => {
      reconnectMs = RECONNECT_MIN_MS;
      if (socket) socket.close();
      else connect();
    });
  }
}

if (typeof module !== "undefined") module.exports = { handle, COMMANDS, connect };

connect();
