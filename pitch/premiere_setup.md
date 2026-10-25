# Premiere Pro stage-demo setup

This checklist prepares the six-beat, fully local Premiere Pro demonstration.
Record the exact Premiere Pro version and build from **Premiere Pro → About
Premiere Pro** on the demo Mac; the Linux development environment cannot verify
Premiere behavior.

## Prepare the Mac

1. Install FFmpeg (`brew install ffmpeg`) and generate the four synthetic clips:
   `bench/demo/premiere_project/make_clips.sh`. Check that `shot1.mp4` is in
   `~/Movies/Muselet Demo/` and `shot2.mp4`–`shot4.mp4` are in
   `~/Desktop/Footage/`.
2. In Premiere, create `~/Movies/Muselet Demo/Muselet Demo.prproj`. Save a
   pristine copy as `~/Movies/Muselet Demo/Muselet Demo template.prproj`; do not
   use the template as the live demo project.
3. Create a sequence named **Muselet Demo**, set it to **1920×1080, 30 fps**,
   import `shot1.mp4`, and put exactly one 10-second clip on V1. Set the
   playhead to **00:00:04:00**.
4. Keep the **Adobe Premiere Pro Default** keyboard layout. In **Premiere
   Pro → Keyboard Shortcuts**, verify that **D** is assigned to **Select Clip
   at Playhead**; assign it if necessary.
5. Set **Cross Dissolve** as the default video transition from the Effects
   panel's **Video Transitions → Dissolve** list. The tool uses Premiere's
   **Sequence → Apply Video Transition** command.
6. Put the Project panel in **List** view. Dock the **Markers** panel where it
   stays visible. Zoom the timeline so the full clip is legible.
7. Manually export once with **H.264**, preset **Match Source – High bitrate**,
   and Location **Desktop**. This lets Premiere remember the demo export
   settings. Delete that test export before running the suite.
8. In macOS **System Settings → Privacy & Security**, grant Muselet
   **Accessibility** and **Automation → System Events** access. Approve the
   prompts on first run. Keep the screen unlocked during live acceptance.

## Six-beat stage script

Start with `Muselet Demo.prproj` open, the playhead at 00:00:04:00, and
`~/Desktop/Footage` populated. Confirm **Yes** at each requested edit.

| Beat | Say exactly | Expected result |
| --- | --- | --- |
| 1 | “import the clips from my Desktop Footage folder” | `shot2`–`shot4` appear in the Project panel |
| 2 | “cut the clip at the playhead” | The V1 clip is split at four seconds |
| 3 | “add a cross dissolve” | A default cross dissolve appears at the cut |
| 4 | “speed this up to 150%” | The selected clip's speed is 150% |
| 5 | “add a marker here called intro” | A named `intro` marker is visible |
| 6 | “export a 1080p H.264 to the Desktop” | `~/Desktop/Muselet Demo.mp4` is a 1080p H.264 export |

The live acceptance suite uses an isolated copy of the template named
`Muselet Demo run.prproj`, not the project you keep open for rehearsal.
The tool asks before every edit by default. `MUSELET_PREMIERE_CONFIRM=project`
can instead approve once per project window title for a single brain process.

The live suite closes only its case-created Premiere process: it sends
Command–Q through System Events, chooses **Don't Save** or **No** if prompted,
and removes only the run-project copy and the export that its precondition
proved absent. Verify the localized prompt buttons and teardown behavior on the
demo Mac before accepting the live result.

## Reset between runs

1. Quit Premiere Pro and choose **Don't Save** for the disposable run project.
2. For a manual rehearsal, copy `Muselet Demo template.prproj` over
   `Muselet Demo.prproj`, then reopen it. For the live suite, its setup step
   creates a fresh run project from the template.
3. Remove only `~/Desktop/Muselet Demo*.mp4` files created by the demo; do not
   delete unrelated Desktop exports. The acceptance-suite teardown removes only
   the known `~/Desktop/Muselet Demo.mp4` that its precondition proved absent.
4. Rewind the playhead to **00:00:04:00** and confirm `~/Desktop/Footage`
   still has `shot2.mp4`–`shot4.mp4`.

## Troubleshooting by beat

| Beat | If it fails | Check |
| --- | --- | --- |
| Import | No clips or dialog timeout | `~/Desktop/Footage` contains non-hidden supported media; Premiere's File → Import dialog is open and accepts Command–Shift–G. |
| Cut | Undo title does not change | The sequence is active, Timeline is visible, and Sequence → Add Edit is enabled at the playhead. |
| Transition | Premiere says to put the playhead on a cut | The playhead is exactly on the new edit and Cross Dissolve is the default video transition. |
| Speed | Speed dialog does not open | A clip is under the playhead, D selects it, and Clip → Speed/Duration is enabled. |
| Marker | Marker name is missing | Markers → Add Marker and Edit Marker open their dialogs; the Markers panel is visible. |
| Export | Export button is not detected or file times out | Export Settings is open, the Export button is visible on the right, the saved preset targets Desktop, and the screen is unlocked. Confirm the resulting MP4 has a 1080-pixel height. |

Menu titles, undo labels, dialog focus, the export button's OCR bounds, and
Premiere teardown must be checked on the actual demo Mac before claiming live
verification.
