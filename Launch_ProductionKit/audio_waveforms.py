import bpy
import os
import subprocess
import gpu
from bpy.app.handlers import persistent
from gpu_extras.batch import batch_for_shader

from . import utility_panel


# Store waveform images for drawing the overlay. These are always sourced
# from the workspace's Sequencer Scene (the master edit), never from an
# arbitrarily active shot scene.
waveform_overlays = []
draw_handler = None
_waveform_source_scene_name = None
_refresh_scheduled = False
_msgbus_owner = object()


def get_waveform_source_scene(context=None):
	"""Return the scene selected as the workspace's Sequencer Scene.
	Blender 5.0+ intentionally separates the active scene from the scene whose
	sequencer is displayed. The latter is the authoritative timeline for a
	master edit, and it may also be the authoritative source for waveforms.
	"""
	context = context or bpy.context
	scene = getattr(context, "sequencer_scene", None)
	if scene is not None:
		return scene
	
	workspace = getattr(context, "workspace", None)
	scene = getattr(workspace, "sequencer_scene", None) if workspace else None
	return scene or getattr(context, "scene", None)


def get_waveform_settings(context=None):
	"""Return settings from the master waveform source, not the active shot."""
	scene = get_waveform_source_scene(context)
	return getattr(scene, "production_kit_settings", None) if scene else None


def _clear_waveform_overlay_data():
	"""Clear cached overlay data without touching on-disk waveform images."""
	global _waveform_source_scene_name
	waveform_overlays.clear()
	_waveform_source_scene_name = None


def _find_time_offset(scene, target_scene, current_frame, visited):
	"""Recursively resolve the frame offset from `scene` down to `target_scene`.

	Walks every Scene Strip in `scene`, descending into the scenes they
	reference until `target_scene` is found, summing the offset at each hop.
	`current_frame` is the playhead position expressed in `scene`'s own frame
	space, used to disambiguate a scene that is used more than once.
	"""
	if scene == target_scene:
		return 0
	if scene is None or not scene.sequence_editor or scene.name in visited:
		return None
	visited = visited | {scene.name}
	
	editor = scene.sequence_editor
	nested_scenes = {
		strip.scene for strip in editor.strips_all
		if strip.type == 'SCENE' and getattr(strip, "scene", None) not in (None, scene)
		and not getattr(strip, "use_reverse_frames", False)
	}
	
	for nested_scene in nested_scenes:
		candidates = [
			strip for strip in editor.strips_all
			if strip.type == 'SCENE' and strip.scene == nested_scene
			and not getattr(strip, "use_reverse_frames", False)
		]
		
		# A scene may be used more than once in an edit. When timeline sync is
		# enabled, the current frame identifies the instance unambiguously.
		active_candidates = [
			strip for strip in candidates
			if strip.frame_final_start <= current_frame < strip.frame_final_end
		]
		if len(active_candidates) == 1:
			strip = active_candidates[0]
		elif len(candidates) == 1:
			strip = candidates[0]
		else:
			continue
		
		# frame_final_start is the first displayed frame in `scene`. Positive
		# strip offsets trim corresponding frames from the nested scene, so add
		# both trim values when converting to the nested scene's local time.
		local_start = (
			nested_scene.frame_start
			+ int(getattr(strip, "frame_offset_start", 0))
			+ int(getattr(strip, "animation_offset_start", 0))
		)
		step_offset = local_start - int(strip.frame_final_start)
		
		result = _find_time_offset(nested_scene, target_scene, current_frame + step_offset, visited)
		if result is not None:
			return step_offset + result
	
	return None


def _scene_strip_time_offset(source_scene, active_scene):
	"""Return the master-to-shot frame offset for the current Scene Strip chain.

	The edit scene owns the audio strips, while an animator often works in a
	shot scene whose timeline starts at frame 0 or 1, possibly several Scene
	Strips deep inside the edit. The returned value converts a frame in the
	master sequencer into the local shot frame.

	Reverse Scene Strips are deliberately left unmapped: accurately displaying a
	reversed waveform requires flipping the image texture, rather than merely
	translating it. Normal and trimmed Scene Strips are supported.
	"""
	if source_scene is None or active_scene is None:
		return None
	if source_scene == active_scene:
		return 0
	return _find_time_offset(source_scene, active_scene, source_scene.frame_current, set())


def _find_scene_with_audio_referencing(target_scene):
	"""Search the whole file for the nearest scene that leads to `target_scene`
	through a chain of Scene Strips and that itself has audio to show -- either
	directly or through its own nested Scene Strips.
	Used by the Parents/All Audio Source scopes. Ancestors are checked
	nearest-first, one generation at a time.
	"""
	if target_scene is None:
		return None
	
	visited = {target_scene.name}
	frontier = [target_scene]
	while frontier:
		parents = []
		for scene in frontier:
			for candidate in bpy.data.scenes:
				if candidate.name in visited or candidate in parents:
					continue
				editor = getattr(candidate, "sequence_editor", None)
				if editor is None:
					continue
				references_scene = any(
					strip.type == 'SCENE' and getattr(strip, "scene", None) == scene
					and not getattr(strip, "use_reverse_frames", False)
					for strip in editor.strips_all
				)
				if references_scene:
					parents.append(candidate)
		
		for candidate in parents:
			if _collect_audio_clips(candidate):
				return candidate
		
		visited.update(parent.name for parent in parents)
		frontier = parents
	
	return None


def _mapped_waveform_overlays(context=None):
	"""Yield cached master overlays translated into the active scene's time."""
	source_scene = get_waveform_source_scene(context)
	active_scene = getattr(context or bpy.context, "scene", None)
	time_offset = _scene_strip_time_offset(source_scene, active_scene)
	
	for overlay in waveform_overlays:
		mapped_overlay = overlay.copy()
		if time_offset is not None:
			mapped_overlay["start"] += time_offset
			mapped_overlay["end"] += time_offset
		yield mapped_overlay


def _tag_timeline_redraw():
	"""Request a redraw after a Sequencer Scene change."""
	window_manager = getattr(bpy.context, "window_manager", None)
	for window in getattr(window_manager, "windows", []):
		for area in getattr(window.screen, "areas", []):
			if area.type in {'DOPESHEET_EDITOR', 'VIEW_3D'}:
				area.tag_redraw()


def _refresh_waveform_source():
	"""Timer callback that refreshes cached data after the source scene changes."""
	global _refresh_scheduled
	_refresh_scheduled = False

	settings = get_waveform_settings()
	if settings and settings.waveform_show:
		generate_waveform_overlay_data()
	else:
		_clear_waveform_overlay_data()
	_tag_timeline_redraw()
	return None


def _schedule_waveform_source_refresh():
	"""Defer source refresh so message-bus callbacks remain inexpensive."""
	global _refresh_scheduled
	if _refresh_scheduled:
		return
	_refresh_scheduled = True
	bpy.app.timers.register(_refresh_waveform_source, first_interval=0.0)


def _on_sequencer_scene_changed():
	"""Message-bus callback for a workspace selecting another Sequencer Scene."""
	_schedule_waveform_source_refresh()


def _subscribe_to_sequencer_scene_changes():
	"""Refresh waveform data when Blender changes the master Sequencer Scene."""
	bpy.msgbus.clear_by_owner(_msgbus_owner)
	try:
		bpy.msgbus.subscribe_rna(
			key=(bpy.types.WorkSpace, "sequencer_scene"),
			owner=_msgbus_owner,
			args=(),
			notify=_on_sequencer_scene_changed,
		)
	except (AttributeError, TypeError, ValueError):
		# The waveform tool still works in Blender versions without the separate
		# Sequencer Scene API; it simply falls back to the active scene.
		pass


def _direct_audio_clips(scene):
	"""Return only `scene`'s own sound strips, mapped into its own frame space.
	This is the Self Audio Source scope: no Scene Strips are followed at all.
	"""
	if scene is None or not scene.sequence_editor:
		return []
	clips = []
	for strip in scene.sequence_editor.strips_all:
		if strip.type == 'SOUND' and strip.sound:
			offset_start = int(strip.frame_offset_start)
			duration = int(strip.frame_final_duration)
			source_duration = max(offset_start + duration + int(strip.frame_offset_end), 1)
			clips.append({
				"sound": strip.sound,
				"start": int(strip.frame_final_start),
				"end": int(strip.frame_final_start) + duration,
				"channel": strip.channel,
				"offset_start": offset_start,
				"source_duration": source_duration,
			})
	return clips


def _collect_audio_clips(scene, time_offset=0, window=None, visited=frozenset()):
	"""Recursively collect sound strips, mapped into the top scene's time space.

	This is the Children Audio Source scope: a Scene Strip can reference a
	scene that has no audio of its own but that, in turn, contains a nested
	Scene Strip pointing at a scene that does. This walks that chain so audio
	is found no matter how deep it is nested.

	`time_offset` converts a frame number local to `scene` into a frame number
	in the top scene's time space. `window` is the (start, end) range, already
	in top-scene time, that a contribution must be clipped to -- the visible
	portion of the Scene Strip that led to `scene` -- or None at the top level.
	"""
	if scene is None or not scene.sequence_editor or scene.name in visited:
		return []
	visited = visited | {scene.name}
	
	clips = []
	for strip in scene.sequence_editor.strips_all:
		if strip.type == 'SOUND':
			if not strip.sound:
				continue
			offset_start = int(strip.frame_offset_start)
			source_duration = max(offset_start + int(strip.frame_final_duration) + int(strip.frame_offset_end), 1)
			start = int(strip.frame_final_start) + time_offset
			end = start + int(strip.frame_final_duration)
			if window is not None:
				clipped_start, clipped_end = max(start, window[0]), min(end, window[1])
				if clipped_start >= clipped_end:
					continue
				# A Scene Strip can show only part of this sound; advance the
				# source-file offset by whatever got clipped off the front so
				# the cropped waveform still matches the audible content.
				offset_start += clipped_start - start
				start, end = clipped_start, clipped_end
			clips.append({
				"sound": strip.sound,
				"start": start,
				"end": end,
				"channel": strip.channel,
				"offset_start": offset_start,
				"source_duration": source_duration,
			})
		elif strip.type == 'SCENE':
			nested_scene = getattr(strip, "scene", None)
			if nested_scene is None or nested_scene == scene:
				continue
			if getattr(strip, "use_reverse_frames", False):
				# Reversed playback cannot be represented by a linear frame
				# offset; skip rather than show a misleading waveform.
				continue
			
			nested_local_start = (
				nested_scene.frame_start
				+ int(getattr(strip, "frame_offset_start", 0))
				+ int(getattr(strip, "animation_offset_start", 0))
			)
			nested_offset = time_offset + int(strip.frame_final_start) - nested_local_start
			
			nested_window = (
				int(strip.frame_final_start) + time_offset,
				int(strip.frame_final_end) + time_offset,
			)
			if window is not None:
				nested_window = (max(nested_window[0], window[0]), min(nested_window[1], window[1]))
			if nested_window[0] >= nested_window[1]:
				continue
			
			clips.extend(_collect_audio_clips(nested_scene, nested_offset, nested_window, visited))
	return clips


def _collect_parent_audio_clips(scene):
	"""Return audio from the nearest edit `scene` is nested inside, mapped into
	`scene`'s own time. This is (part of) the Parents/All Audio Source scopes.
	`scene`'s own branch is excluded from the ancestor's collection so it is
	never duplicated with what the Self/Children scopes already show.
	"""
	if scene is None:
		return []
	host = _find_scene_with_audio_referencing(scene)
	if host is None:
		return []
	offset = _scene_strip_time_offset(host, scene)
	if offset is None:
		return []
	host_clips = _collect_audio_clips(host, visited=frozenset({scene.name}))
	return [
		{**clip, "start": clip["start"] + offset, "end": clip["end"] + offset}
		for clip in host_clips
	]


def get_audio_clips(scene=None):
	"""Retrieve sound strips for `scene`, honoring its Audio Source scope.
	Defaults to the Self scope (the scene's own sequencer only) when the scene
	has no production_kit_settings to read a scope from.
	"""
	scene = scene or get_waveform_source_scene()
	if scene is None:
		return []
	
	settings = getattr(scene, "production_kit_settings", None)
	scope = getattr(settings, "waveform_audio_scope", 'SELF') if settings else 'SELF'
	
	if scope == 'CHILDREN':
		return _collect_audio_clips(scene)
	if scope == 'PARENTS':
		return _direct_audio_clips(scene) + _collect_parent_audio_clips(scene)
	if scope == 'ALL':
		return _collect_audio_clips(scene) + _collect_parent_audio_clips(scene)
	return _direct_audio_clips(scene)


def generate_waveform_image(audio_path, width, height, image_path):
	"""Generate a waveform image using FFmpeg with the defined parameters."""
	prefs = bpy.context.preferences.addons[__package__].preferences
	
	ffmpeg_cmd = [
		prefs.ffmpeg_location, "-i", audio_path,
		"-filter_complex",
		f"aformat=channel_layouts=mono,loudnorm=I=-16:TP=-1:LRA=2,showwavespic=s={width}x{height}:colors=white@1,scale={width}:{height}",
		"-frames:v", "1", "-pix_fmt", "rgba",
		"-y", image_path
	]
	
	try:
		subprocess.run(ffmpeg_cmd, check=True)
		return image_path
	except subprocess.CalledProcessError:
		print(f"Failed to generate waveform for {audio_path}")
		return None


def generate_waveform_overlay_data(source_scene=None):
	"""Load or generate waveform images for the master Sequencer Scene.
	Existing cached waveform images on disk are loaded immediately without
	re-running FFmpeg. FFmpeg is only called when the image file is absent.
	"""
	global _waveform_source_scene_name
	source_scene = source_scene or get_waveform_source_scene()
	_clear_waveform_overlay_data()
	if source_scene is None:
		return
	_waveform_source_scene_name = source_scene.name
	
	prefs = bpy.context.preferences.addons[__package__].preferences
	
	for clip in get_audio_clips(source_scene):
		audio_path = bpy.path.abspath(clip["sound"].filepath)
		audio_path = os.path.realpath(audio_path)
		image_path = os.path.splitext(audio_path)[0] + "_waveform.png"
		
		if not os.path.isfile(audio_path):
			continue
		
		if os.path.isfile(image_path):
			# Cached image already exists — use it directly without re-generating.
			# Also purge any stale Blender-internal image block so the file on disk
			# is always the authoritative source when we load it in draw_waveforms().
			existing_img = bpy.data.images.get(image_path)
			if existing_img:
				bpy.data.images.remove(existing_img)
		else:
			# No cached image — generate it now via FFmpeg. The image always
			# covers the whole source file (not just this clip's trimmed
			# range) so it can be cached and shared by other strips that
			# trim the same file differently; draw_waveforms() crops it.
			width = max(1, int(clip["source_duration"] * prefs.waveform_size_x))
			height = int(prefs.waveform_size_y)
			image_path = generate_waveform_image(audio_path, width, height, image_path)

		if image_path and os.path.exists(image_path):
			waveform_overlays.append({
				"start": clip["start"],
				"end": clip["end"],
				"channel": clip["channel"],
				"image": image_path,
				"source_scene": source_scene.name,
				"offset_start": clip["offset_start"],
				"source_duration": clip["source_duration"],
			})
	_tag_timeline_redraw()


def draw_waveforms():
	"""Draw mapped waveforms as overlays in the Dopesheet/Timeline."""
	source_scene = get_waveform_source_scene()
	settings = get_waveform_settings()
	
	# Do not draw a waveform from the previously selected master scene while
	# Blender's deferred refresh is pending.
	if source_scene is None or _waveform_source_scene_name != source_scene.name:
		_schedule_waveform_source_refresh()
		return
	
	if not settings or not settings.waveform_show or not waveform_overlays:
		return
	
	prefs = bpy.context.preferences.addons[__package__].preferences
	shader = gpu.shader.from_builtin('IMAGE_COLOR')
	
	for overlay in _mapped_waveform_overlays():
		try:
			# Get image data
			img = bpy.data.images.get(overlay["image"])
			if not img:
				img = bpy.data.images.load(overlay["image"], check_existing=True)
			
			if img.size[0] == 0 or img.size[1] == 0:
				print(f"Image size is invalid: {overlay['image']}")
				continue
			
			# Convert to GPU texture
			texture = gpu.texture.from_image(img)
			if not texture:
				print(f"Failed to create GPU texture for {overlay['image']}")
				continue
			
			# Create mesh for display
			start_x = overlay["start"]
			end_x = overlay["end"]
			screen_x_start = bpy.context.region.view2d.view_to_region(start_x, 0, clip=False)[0]
			screen_x_end = bpy.context.region.view2d.view_to_region(end_x, 0, clip=False)[0]
			
			height_scaled = prefs.waveform_size_y * settings.waveform_display_scale
			screen_y = settings.waveform_display_offset - height_scaled + (overlay["channel"] * height_scaled * 0.5)

			# The image covers the whole source file; sample only the
			# trimmed window that is actually audible on the timeline.
			source_duration = overlay.get("source_duration") or (end_x - start_x) or 1
			offset_start = overlay.get("offset_start", 0)
			u_start = offset_start / source_duration
			u_end = (offset_start + (end_x - start_x)) / source_duration

			# Create shader batch
			batch = batch_for_shader(shader, 'TRI_FAN', {
				"pos": [
					(screen_x_start, screen_y),
					(screen_x_end, screen_y),
					(screen_x_end, screen_y + height_scaled),
					(screen_x_start, screen_y + height_scaled)
				],
				"texCoord": [(u_start, 0), (u_end, 0), (u_end, 1), (u_start, 1)]
			})
			
			# Bind texture and apply color tint with alpha
			gpu.state.blend_set('ALPHA')
			shader.bind()
			shader.uniform_sampler("image", texture)
			shader.uniform_float("color", settings.waveform_display_color)
			batch.draw(shader)
			gpu.state.blend_set('NONE')
		
		except Exception as e:
			print(f"Error rendering waveform: {e}")


class RegenerateWaveformsOperator(bpy.types.Operator):
	"""Regenerate all waveform images from source audio files"""
	bl_idname = "timeline.regenerate_waveforms"
	bl_label = "Regenerate Waveforms"
	
	def execute(self, context):
		# Delete cached waveform images so they get regenerated fresh
		source_scene = get_waveform_source_scene(context)
		for clip in get_audio_clips(source_scene):
			audio_path = bpy.path.abspath(clip["sound"].filepath)
			audio_path = os.path.realpath(audio_path)
			image_path = os.path.splitext(audio_path)[0] + "_waveform.png"
			if os.path.isfile(image_path):
				os.remove(image_path)
			img = bpy.data.images.get(image_path)
			if img:
				bpy.data.images.remove(img)
		generate_waveform_overlay_data(source_scene)
		return {'FINISHED'}


@persistent
def _on_load_post(*args):
	"""Rebind to the master Sequencer Scene after a project is opened."""
	# Message-bus subscriptions are cleared on file load. Delay registration
	# until the workspace and its Sequencer Scene are fully available.
	def _deferred():
		try:
			_subscribe_to_sequencer_scene_changes()
			_refresh_waveform_source()
		except Exception as e:
			print(f"Waveform load_post error: {e}")
		return None
	bpy.app.timers.register(_deferred, first_interval=0.1)


def _draw_waveform_ui(layout, context):
	"""Shared UI drawing for waveform panels."""
	source_scene = get_waveform_source_scene(context)
	settings = get_waveform_settings(context)
	if settings is None:
		return
	
	if source_scene and source_scene != context.scene:
		layout.label(text=f"Source: {source_scene.name} (mapped)", icon="SEQUENCE")
	
	layout.prop(settings, "waveform_audio_scope", expand=True)
	
	row = layout.row(align=True)
	row.prop(settings, "waveform_display_color", text="", icon="MOD_TINT")
	row.prop(settings, "waveform_display_scale", text="Scale", icon="VIEW_PERSPECTIVE")
	row.prop(settings, "waveform_display_offset", text="Offset", icon="MOD_ARRAY")
	row.operator("timeline.regenerate_waveforms", text="", icon="FILE_REFRESH")


class DOPESHEET_PT_waveform_display(bpy.types.Panel):
	"""Waveform UI Panel in Dopesheet sidebar"""
	bl_label = "Audio Waveforms"
	bl_idname = "DOPESHEET_PT_waveform_display"
	bl_space_type = "DOPESHEET_EDITOR"
	bl_region_type = "UI"
	bl_category = "Launch"
	bl_order = 20
	bl_options = {'DEFAULT_CLOSED'}
	category_preference = "overlays_category_dopesheet"
	
	@classmethod
	def poll(cls, context):
		return context.preferences.addons[__package__].preferences.ffmpeg_processing
	
	def draw_header(self, context):
		settings = get_waveform_settings(context)
		if settings:
			self.layout.prop(settings, "waveform_show", text="")
	
	def draw(self, context):
		_draw_waveform_ui(self.layout, context)


# ---------------------------------------------------------------------------
# Register classes
# ---------------------------------------------------------------------------

classes = [RegenerateWaveformsOperator]
panels = [DOPESHEET_PT_waveform_display]


def register():
	# Register classes
	for cls in classes:
		bpy.utils.register_class(cls)
	# Register panels
	utility_panel.register_panels(panels)
	
	global draw_handler
	if draw_handler is None:
		draw_handler = bpy.types.SpaceDopeSheetEditor.draw_handler_add(
			draw_waveforms, (), 'WINDOW', 'POST_PIXEL'
		)
	if _on_load_post not in bpy.app.handlers.load_post:
		bpy.app.handlers.load_post.append(_on_load_post)
	_subscribe_to_sequencer_scene_changes()


def unregister():
	global draw_handler, _refresh_scheduled
	if draw_handler is not None:
		bpy.types.SpaceDopeSheetEditor.draw_handler_remove(draw_handler, 'WINDOW')
		draw_handler = None
	if _on_load_post in bpy.app.handlers.load_post:
		bpy.app.handlers.load_post.remove(_on_load_post)
	if bpy.app.timers.is_registered(_refresh_waveform_source):
		bpy.app.timers.unregister(_refresh_waveform_source)
	_refresh_scheduled = False
	bpy.msgbus.clear_by_owner(_msgbus_owner)
	_clear_waveform_overlay_data()
	
	# Unregister panels
	utility_panel.unregister_panels(panels)
	# Unregister classes
	for cls in reversed(classes):
		bpy.utils.unregister_class(cls)


if __name__ == "__main__":
	try:
		unregister()
	except Exception:
		pass
	register()
