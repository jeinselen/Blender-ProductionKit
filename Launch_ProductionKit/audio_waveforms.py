import bpy
import os
import subprocess
import gpu
from gpu_extras.batch import batch_for_shader

# Store waveform images to be drawn
waveform_overlays = []
draw_handler = None

def get_audio_clips():
	"""Retrieve all audio clips from the Blender sequencer."""
	scene = bpy.context.scene
	if not scene.sequence_editor:
		return []
	return [strip for strip in scene.sequence_editor.sequences_all if strip.type == 'SOUND']


def generate_waveform(audio_path, width, height):
	"""Generate a waveform image using FFmpeg with the given parameters."""
	waveform_path = os.path.splitext(audio_path)[0] + "_waveform.png"
	
	color_rgba = f"white@1"
	
	ffmpeg_cmd = [
		"ffmpeg", "-i", audio_path,
		"-filter_complex",
		f"aformat=channel_layouts=mono,showwavespic=s={width}x{height}:colors={color_rgba}",
		"-frames:v", "1", "-pix_fmt", "rgba",
		"-y", waveform_path
	]
	
	# Use the "-n" command to NEVER overwrite files instead of YEAH, SURE, WHY NOT overwrite files with the "-y" commend
	# May need a switchable option, or use -n on the general "turn on waveforms" and "-y" on the "regenerate all" command
	
	try:
		subprocess.run(ffmpeg_cmd, check=True)
		return waveform_path
	except subprocess.CalledProcessError:
		print(f"Failed to generate waveform for {audio_path}")
		return None


def generate_waveform_overlay_data():
	"""Generate waveform images and prepare overlay data for drawing in the Timeline."""
	global waveform_overlays
	waveform_overlays.clear()
	
	prefs = bpy.context.preferences.addons[__package__].preferences
#	settings = bpy.context.scene.production_kit_settings
	
	for clip in get_audio_clips():
		audio_path = str(clip.sound.filepath)
		audio_path = os.path.realpath(bpy.path.abspath(audio_path))
		
		width = int(clip.frame_final_duration * prefs.waveform_size_x)  # Match the length of the clip in frames
		height = int(prefs.waveform_size_y)
		
		waveform_path = generate_waveform(audio_path, width, height)
		
		if waveform_path and os.path.exists(waveform_path):
			waveform_overlays.append({
				"start": int(clip.frame_start),
				"end": int(clip.frame_start) + int(clip.frame_final_duration),
				"channel": clip.channel,
				"image": waveform_path
			})


def draw_waveforms():
	"""Draw waveforms as overlays in the Timeline (Dopesheet)."""
	if not waveform_overlays:
		return
	
	prefs = bpy.context.preferences.addons[__package__].preferences
#	settings = bpy.context.scene.production_kit_settings
	
	# Use Blender's built-in IMAGE_COLOR shader
	shader = gpu.shader.from_builtin('IMAGE_COLOR')
	
	for overlay in waveform_overlays:
		try:
			img = bpy.data.images.get(overlay["image"])
			if not img:
				img = bpy.data.images.load(overlay["image"], check_existing=True)
				
			if img.size[0] == 0 or img.size[1] == 0:
				print(f"🚨 Image size is invalid: {overlay['image']}")
				continue
			
			tex = gpu.texture.from_image(img)
			if not tex:
				print(f"🚨 Failed to create GPU texture for {overlay['image']}")
				continue
			
			print(f"✅ Successfully created GPU texture for {overlay['image']}")
			
			region = bpy.context.region
			if not region:
				continue
			
			start_x = overlay["start"]
			end_x = overlay["end"]
			screen_x_start = bpy.context.region.view2d.view_to_region(start_x, 0, clip=True)[0]
			screen_x_end = bpy.context.region.view2d.view_to_region(end_x, 0, clip=True)[0]
			
			screen_y = 50 - (overlay["channel"] * 10)  # Offset each channel
			height_scaled = prefs.waveform_size_y * prefs.waveform_display_scale  # Scale the waveform height
			
			# Create shader batch
			batch = batch_for_shader(shader, 'TRI_FAN', {
				"pos": [(screen_x_start, screen_y), (screen_x_end, screen_y),
						(screen_x_end, screen_y + height_scaled), (screen_x_start, screen_y + height_scaled)],
				"texCoord": [(0, 0), (1, 0), (1, 1), (0, 1)]
			})
			
			# Bind texture and apply color tint with alpha
			shader.bind()
			shader.uniform_sampler("image", tex)
			shader.uniform_float("color", prefs.waveform_display_color)  # Color + Opacity
			batch.draw(shader)
			
		except Exception as e:
			print(f"Error rendering waveform: {e}")


def register_draw_handler():
	"""Register OpenGL draw handler for the Timeline (Dopesheet)."""
	global draw_handler
	if draw_handler is None:
		draw_handler = bpy.types.SpaceDopeSheetEditor.draw_handler_add(draw_waveforms, (), 'WINDOW', 'POST_PIXEL')


def unregister_draw_handler():
	"""Unregister OpenGL draw handler to remove waveforms."""
	global draw_handler
	if draw_handler:
		bpy.types.SpaceDopeSheetEditor.draw_handler_remove(draw_handler, 'WINDOW')
		draw_handler = None


class GenerateTimelineWaveformsOperator(bpy.types.Operator):
	"""Generate and Display Waveforms in Timeline"""
	bl_idname = "timeline.generate_waveform_overlay"
	bl_label = "Generate Timeline Waveforms"
	
	def execute(self, context):
		generate_waveform_overlay_data()
		register_draw_handler()
		return {'FINISHED'}


class RemoveTimelineWaveformsOperator(bpy.types.Operator):
	"""Remove all waveform overlays from the Timeline"""
	bl_idname = "timeline.remove_waveform_overlay"
	bl_label = "Remove Timeline Waveforms"
	
	def execute(self, context):
		unregister_draw_handler()
		return {'FINISHED'}


class DOPESHEET_PT_waveform_display(bpy.types.Panel):
	"""Waveform UI Panel in Timeline"""
	bl_label = "Timeline Waveforms"
	bl_idname = "DOPESHEET_PT_waveform_display"
	bl_space_type = 'DOPESHEET_EDITOR'
	bl_region_type = 'UI'
	bl_category = "Display"
	
	def draw(self, context):
		prefs = context.preferences.addons[__package__].preferences
	#	settings = context.scene.production_kit_settings
		
		layout = self.layout
		layout.prop(prefs, "waveform_display_color")
		layout.prop(prefs, "waveform_display_scale")
		layout.prop(prefs, "waveform_display_offset")
		layout.operator("timeline.generate_waveform_overlay", text="Generate Timeline Waveforms", icon="SOUND")
		layout.operator("timeline.remove_waveform_overlay", text="Remove Waveforms", icon="X")


# Register classes
classes = [GenerateTimelineWaveformsOperator, RemoveTimelineWaveformsOperator, DOPESHEET_PT_waveform_display]


def register():
	for cls in classes:
		bpy.utils.register_class(cls)


def unregister():
	for cls in classes:
		bpy.utils.unregister_class(cls)


if __name__ == "__main__":
	register()