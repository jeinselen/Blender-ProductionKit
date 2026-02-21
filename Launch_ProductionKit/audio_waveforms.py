import bpy
import os
import subprocess
import gpu
from gpu_extras.batch import batch_for_shader

# Store waveform images for drawing the overlay
waveform_overlays = []
draw_handler = None



def get_audio_clips():
	"""Retrieve all audio clips from the Blender sequencer."""
	# Blender 5.0: context.scene may differ from the VSE scene; use context.sequencer_scene (falls back to context.scene on older builds)
	scene = getattr(bpy.context, 'sequencer_scene', None) or bpy.context.scene
	if not scene.sequence_editor:
		return []
	return [strip for strip in scene.sequence_editor.strips_all if strip.type == 'SOUND']
	
	name
	bpy.data.scenes["Scene"].name
	bpy.data.scenes["Scene"].name



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
#		subprocess.run(ffmpeg_cmd, check=True, capture_output=True)
		return image_path
	except subprocess.CalledProcessError:
		print(f"Failed to generate waveform for {audio_path}")
		return None



def generate_waveform_overlay_data():
	"""Load or generate waveform images and prepare overlay data for drawing.
	Existing cached waveform images on disk are loaded immediately without
	re-running FFmpeg.  FFmpeg is only called when the image file is absent.
	"""
	global waveform_overlays
	waveform_overlays.clear()
	
	prefs = bpy.context.preferences.addons[__package__].preferences
	
	for clip in get_audio_clips():
		audio_path = bpy.path.abspath(clip.sound.filepath)
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
			# No cached image — generate it now via FFmpeg.
			width = int(clip.frame_final_duration * prefs.waveform_size_x)
			height = int(prefs.waveform_size_y)
			image_path = generate_waveform_image(audio_path, width, height, image_path)
		
		if image_path and os.path.exists(image_path):
			waveform_overlays.append({
				"start": int(clip.frame_start),
				"end": int(clip.frame_start) + int(clip.frame_final_duration),
				"channel": clip.channel,
				"image": image_path
			})



def draw_waveforms():
	"""Draw waveforms as overlays in the Dopesheet/Timeline."""
	settings = bpy.context.scene.production_kit_settings
	
	# If not enabled or waveforms are not loaded, return (instead of registering/unregistering)
	if not settings.waveform_show or not waveform_overlays:
		return
	
	prefs = bpy.context.preferences.addons[__package__].preferences
	shader = gpu.shader.from_builtin('IMAGE_COLOR')
	
	for overlay in waveform_overlays:
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
			
			height_scaled = prefs.waveform_size_y * settings.waveform_display_scale  # Scale the waveform height
			screen_y = settings.waveform_display_offset - height_scaled + (overlay["channel"] * height_scaled * 0.5) # Offset each channel
			
			# Create shader batch
			batch = batch_for_shader(shader, 'TRI_FAN', {
				"pos": [
					(screen_x_start, screen_y),
					(screen_x_end, screen_y),
					(screen_x_end, screen_y + height_scaled),
					(screen_x_start, screen_y + height_scaled)
				],
				"texCoord": [(0, 0), (1, 0), (1, 1), (0, 1)]
			})
			
			# Bind texture and apply color tint with alpha
			gpu.state.blend_set('ALPHA') # https://docs.blender.org/api/current/gpu.state.html
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
		for clip in get_audio_clips():
			audio_path = bpy.path.abspath(clip.sound.filepath)
			audio_path = os.path.realpath(audio_path)
			image_path = os.path.splitext(audio_path)[0] + "_waveform.png"
			if os.path.isfile(image_path):
				os.remove(image_path)
			img = bpy.data.images.get(image_path)
			if img:
				bpy.data.images.remove(img)
		generate_waveform_overlay_data()
		return {'FINISHED'}



def _on_load_post(*args):
	"""App handler: reload waveform data when a project is opened, if enabled."""
	# Use a depsgraph-update-queued timer so scene properties are fully available.
	def _deferred():
		try:
			settings = bpy.context.scene.production_kit_settings
			if settings.waveform_show:
				generate_waveform_overlay_data()
		except Exception as e:
			print(f"Waveform load_post error: {e}")
	bpy.app.timers.register(_deferred, first_interval=0.1)



def _draw_waveform_ui(layout, context):
	"""Shared UI drawing for waveform panels."""
	prefs = context.preferences.addons[__package__].preferences
	settings = bpy.context.scene.production_kit_settings
	
	row = layout.row(align=True)
	row.prop(settings, "waveform_display_color", text="", icon="MOD_TINT") # MOD_TINT COLOR RESTRICT_COLOR_OFF RESTRICT_COLOR_ON
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
	
	@classmethod
	def poll(cls, context):
		return context.preferences.addons[__package__].preferences.ffmpeg_processing
	
	def draw_header(self, context):
		self.layout.prop(context.scene.production_kit_settings, "waveform_show", text="")
		
	def draw(self, context):
		_draw_waveform_ui(self.layout, context)



# ---------------------------------------------------------------------------
# Register classes
# ---------------------------------------------------------------------------

classes = [
	RegenerateWaveformsOperator,
	DOPESHEET_PT_waveform_display,
]


def register():
	for cls in classes:
		bpy.utils.register_class(cls)
	global draw_handler
	if draw_handler is None:
		draw_handler = bpy.types.SpaceDopeSheetEditor.draw_handler_add(
			draw_waveforms, (), 'WINDOW', 'POST_PIXEL'
		)
	if _on_load_post not in bpy.app.handlers.load_post:
		bpy.app.handlers.load_post.append(_on_load_post)


def unregister():
	global draw_handler
	if draw_handler is not None:
		bpy.types.SpaceDopeSheetEditor.draw_handler_remove(draw_handler, 'WINDOW')
		draw_handler = None
	if _on_load_post in bpy.app.handlers.load_post:
		bpy.app.handlers.load_post.remove(_on_load_post)
	for cls in reversed(classes):
		bpy.utils.unregister_class(cls)


if __name__ == "__main__":
	register()