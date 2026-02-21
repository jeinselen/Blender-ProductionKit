import bpy
import gpu
from gpu_extras.batch import batch_for_shader
import math



# ---------------------------------------------------------------------------
# Geometry builders  (all return flat list of (x,y) TRIS vertices)
# ---------------------------------------------------------------------------

_CIRCLE_SEGMENTS = 16

def _circle_verts(cx, cy, r):
	r *= 0.875 # Scale circles smaller than the rest to maintain more equal visual prominance
	verts = []
	for i in range(_CIRCLE_SEGMENTS):
		a0 = (i     / _CIRCLE_SEGMENTS) * math.tau
		a1 = ((i+1) / _CIRCLE_SEGMENTS) * math.tau
		verts.append((cx, cy))
		verts.append((cx + math.cos(a0) * r, cy + math.sin(a0) * r))
		verts.append((cx + math.cos(a1) * r, cy + math.sin(a1) * r))
	return verts

def _diamond_verts(cx, cy, r):
	c  = (cx,     cy    )
	t  = (cx,     cy + r)
	ri = (cx + r, cy    )
	b  = (cx,     cy - r)
	l  = (cx - r, cy    )
	return [t, ri, c,   ri, b, c,   b, l, c,   l, t, c]

def _rectangle_verts(cx, cy, r):
	h = r * 0.5
	tl = (cx - h, cy + r)
	tr = (cx + h, cy + r)
	br = (cx + h, cy - r)
	bl = (cx - h, cy - r)
	return [tl, tr, br,   tl, br, bl]

def _triup_verts(cx, cy, r):
	t = (cx, cy + r)
	br = (cx + r, cy - r)
	bl = (cx - r, cy - r)
	return [t, bl, br]

def _tridown_verts(cx, cy, r):
	tl = (cx - r, cy + r)
	tr = (cx + r, cy + r)
	b = (cx, cy - r)
	return [tl, tr, b]

_SHAPE_BUILDERS = {
	"CIRCLE":  _circle_verts,
	"DIAMOND": _diamond_verts,
	"RECTANGLE":  _rectangle_verts,
	"TRIUP":  _triup_verts,
	"TRIDOWN":  _tridown_verts,
}



# ---------------------------------------------------------------------------
# Draw callback — registered once on SpaceDopeSheetEditor,
# which covers both the Dope Sheet and Timeline modes.
# ---------------------------------------------------------------------------

def draw_bpm_overlay():
	context = bpy.context
	
	if not context.area or context.area.type != 'DOPESHEET_EDITOR':
		return
	
	settings = context.scene.production_kit_settings
	if not settings.bpm_show:
		return
	
	region = context.region
	if not region or region.type != 'WINDOW':
		return
	
	view2d = region.view2d
	scene  = context.scene
	fps    = scene.render.fps / scene.render.fps_base
	
	beat_frames = (60.0 / settings.bpm_speed) * fps
	if beat_frames <= 0:
		return
	
	frame_start = scene.frame_start
	frame_end   = scene.frame_end
	time_offset = settings.bpm_time_offset
	measure     = settings.bpm_measure
	
	first_beat = math.ceil( (frame_start - time_offset) / beat_frames)
	last_beat  = math.floor((frame_end   - time_offset) / beat_frames)
	
	max_size  = max(settings.bpm_beat_size, settings.bpm_measure_size)
	base_y    = 12.0 + settings.bpm_display_offset
	region_w  = region.width
	
	beat_build    = _SHAPE_BUILDERS.get(settings.bpm_beat_shape,    _circle_verts)
	measure_build = _SHAPE_BUILDERS.get(settings.bpm_measure_shape, _circle_verts)
	
	beat_verts    = []
	measure_verts = []
	
	for idx in range(first_beat, last_beat + 1):
		frame = time_offset + idx * beat_frames
		x, _ = view2d.view_to_region(frame, 0, clip=False)
		if x < -max_size or x > region_w + max_size:
			continue
		if idx % measure == 0:
			measure_verts.extend(measure_build(x, base_y, settings.bpm_measure_size))
		else:
			beat_verts.extend(beat_build(x, base_y, settings.bpm_beat_size))
			
	if not beat_verts and not measure_verts:
		return
	
	shader = gpu.shader.from_builtin('UNIFORM_COLOR')
	gpu.state.blend_set('ALPHA')
	
	if beat_verts:
		batch = batch_for_shader(shader, 'TRIS', {"pos": beat_verts})
		shader.bind()
		shader.uniform_float("color", settings.bpm_beat_color)
		batch.draw(shader)
		
	if measure_verts:
		batch = batch_for_shader(shader, 'TRIS', {"pos": measure_verts})
		shader.bind()
		shader.uniform_float("color", settings.bpm_measure_color)
		batch.draw(shader)
		
	gpu.state.blend_set('NONE')



# ---------------------------------------------------------------------------
# N-panel  (DOPESHEET_EDITOR covers both Dope Sheet and Timeline tabs)
# ---------------------------------------------------------------------------

class BPM_PT_panel(bpy.types.Panel):
	bl_label = "BPM Overlay"
	bl_idname = "BPM_PT_panel"
	bl_space_type = "DOPESHEET_EDITOR"
	bl_region_type = "UI"
	bl_category = "Launch"
	
	def draw_header(self, context):
		self.layout.prop(context.scene.production_kit_settings, "bpm_show", text="")
	
	def draw(self, context):
		layout = self.layout
		settings = context.scene.production_kit_settings
		scene  = context.scene
		
		row = layout.row()
		row.prop(settings, "bpm_speed")
		row.prop(settings, "bpm_measure")
		
		row = layout.row()
		row.prop(settings, "bpm_time_offset")
		row.prop(settings, "bpm_display_offset")
		
		row = layout.row(align=True)
		row.label(text="Beat") # icon='KEYFRAME'
		row.prop(settings, "bpm_beat_color", text="")
		row.prop(settings, "bpm_beat_size", text="")
		row.prop(settings, "bpm_beat_shape", text="")
		
		row = layout.row(align=True)
		row.label(text="Measure") # icon='KEYFRAME_HLT'
		row.prop(settings, "bpm_measure_color", text="")
		row.prop(settings, "bpm_measure_size", text="")
		row.prop(settings, "bpm_measure_shape", text="")



# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

_CLASSES = [
	BPM_PT_panel,
]

_draw_handle = None

def register():
	global _draw_handle
	for cls in _CLASSES:
		bpy.utils.register_class(cls)
	
	_draw_handle = bpy.types.SpaceDopeSheetEditor.draw_handler_add(
		draw_bpm_overlay, (), 'WINDOW', 'POST_PIXEL'
	)

def unregister():
	global _draw_handle
	if _draw_handle is not None:
		bpy.types.SpaceDopeSheetEditor.draw_handler_remove(_draw_handle, 'WINDOW')
		_draw_handle = None
	
	for cls in reversed(_CLASSES):
		bpy.utils.unregister_class(cls)

if __name__ == "__main__":
	try:
		unregister()
	except Exception:
		pass
	register()