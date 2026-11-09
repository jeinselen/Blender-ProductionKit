import bpy
import gpu
from gpu_extras.batch import batch_for_shader
import math

from . import utility_panel



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
	"CIRCLE": _circle_verts,
	"DIAMOND": _diamond_verts,
	"RECTANGLE": _rectangle_verts,
	"TRIUP": _triup_verts,
	"TRIDOWN": _tridown_verts,
}



# ---------------------------------------------------------------------------
# Draw callback — registered on SpaceDopeSheetEditor (Dope Sheet and Timeline
# modes), SpaceSequenceEditor (Sequencer strips view), SpaceGraphEditor
# (Graph Editor) and SpaceNLA (NLA Editor).
# ---------------------------------------------------------------------------

_SUPPORTED_AREA_TYPES = {'DOPESHEET_EDITOR', 'SEQUENCE_EDITOR', 'GRAPH_EDITOR', 'NLA_EDITOR'}

def _overlay_scene(context):
	"""In the Sequencer, use the displayed sequencer scene rather than the active
	scene, which Blender 5.x swaps to whichever scene strip is under the playhead
	when "Sync Scene Time" is enabled."""
	if context.area and context.area.type == 'SEQUENCE_EDITOR':
		return getattr(context, "sequencer_scene", None) or context.scene
	return context.scene

def draw_bpm_overlay():
	context = bpy.context

	if not context.area or context.area.type not in _SUPPORTED_AREA_TYPES:
		return
	
	scene = _overlay_scene(context)
	settings = scene.production_kit_settings
	if not settings.bpm_show:
		return
	
	region = context.region
	if not region or region.type != 'WINDOW':
		return
	
	view2d = region.view2d
	fps = scene.render.fps / scene.render.fps_base
	
	beat_frames = (60.0 / settings.bpm_speed) * fps
	if beat_frames <= 0:
		return
	
	frame_start = scene.frame_start
	frame_end = scene.frame_end
	time_offset = settings.bpm_time_offset
	measure = settings.bpm_measure
	
	first_beat = math.ceil( (frame_start - time_offset) / beat_frames)
	last_beat = math.floor((frame_end   - time_offset) / beat_frames)
	
	max_size = max(settings.bpm_beat_size, settings.bpm_measure_size)
	base_y = 12.0 + settings.bpm_display_offset
	region_w = region.width
	
	beat_build = _SHAPE_BUILDERS.get(settings.bpm_beat_shape,    _circle_verts)
	measure_build = _SHAPE_BUILDERS.get(settings.bpm_measure_shape, _circle_verts)
	
	beat_verts = []
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

	# The Sequencer (and other editors) can leave a GL scissor rect active from
	# drawing strip previews/thumbnails or cache indicators; without resetting
	# it here, the overlay gets silently clipped to whatever box was left over.
	gpu.state.scissor_test_set(False)

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
# Shared UI drawing function
# ---------------------------------------------------------------------------

def _draw_bpm_ui(layout, context):
	"""Shared UI drawing for BPM panel — used in both Dopesheet and 3D view."""
	settings = _overlay_scene(context).production_kit_settings
	
	row = layout.row(align=True)
	row.prop(settings, "bpm_speed")
	row.prop(settings, "bpm_measure")
	
	row = layout.row(align=True)
	row.prop(settings, "bpm_time_offset")
	row.prop(settings, "bpm_display_offset")
	
	row = layout.row(align=True)
	row.label(text="Beat")
	row.prop(settings, "bpm_beat_color", text="", icon="MOD_TINT")
	row.prop(settings, "bpm_beat_size", text="")
	row.prop(settings, "bpm_beat_shape", text="")
	
	row = layout.row(align=True)
	row.label(text="Measure")
	row.prop(settings, "bpm_measure_color", text="", icon="MOD_TINT")
	row.prop(settings, "bpm_measure_size", text="")
	row.prop(settings, "bpm_measure_shape", text="")



# ---------------------------------------------------------------------------
# UI Panel for the Dopesheet view
# ---------------------------------------------------------------------------
	
class BPM_PT_panel(bpy.types.Panel):
	bl_label = "BPM Overlay"
	bl_idname = "BPM_PT_panel"
	bl_space_type = "DOPESHEET_EDITOR"
	bl_region_type = "UI"
	bl_category = "Launch"
	bl_order = 21
	bl_options = {'DEFAULT_CLOSED'}
	category_preference = "overlays_category_dopesheet"
	
	def draw_header(self, context):
		self.layout.prop(_overlay_scene(context).production_kit_settings, "bpm_show", text="")
		
	def draw(self, context):
		_draw_bpm_ui(self.layout, context)



# ---------------------------------------------------------------------------
# UI Panel for the Sequencer view
# ---------------------------------------------------------------------------

class SEQUENCER_PT_bpm_panel(bpy.types.Panel):
	bl_label = "BPM Overlay"
	bl_idname = "SEQUENCER_PT_bpm_panel"
	bl_space_type = "SEQUENCE_EDITOR"
	bl_region_type = "UI"
	bl_category = "Launch"
	bl_order = 21
	bl_options = {'DEFAULT_CLOSED'}
	category_preference = "overlays_category_sequencer"

	@classmethod
	def poll(cls, context):
		return context.area is not None and context.area.type == 'SEQUENCE_EDITOR'

	def draw_header(self, context):
		self.layout.prop(_overlay_scene(context).production_kit_settings, "bpm_show", text="")

	def draw(self, context):
		_draw_bpm_ui(self.layout, context)



# ---------------------------------------------------------------------------
# UI Panel for the Graph Editor view
# ---------------------------------------------------------------------------

class GRAPH_PT_bpm_panel(bpy.types.Panel):
	bl_label = "BPM Overlay"
	bl_idname = "GRAPH_PT_bpm_panel"
	bl_space_type = "GRAPH_EDITOR"
	bl_region_type = "UI"
	bl_category = "Launch"
	bl_order = 21
	bl_options = {'DEFAULT_CLOSED'}
	category_preference = "overlays_category_graph"

	@classmethod
	def poll(cls, context):
		return context.area is not None and context.area.type == 'GRAPH_EDITOR'

	def draw_header(self, context):
		self.layout.prop(_overlay_scene(context).production_kit_settings, "bpm_show", text="")

	def draw(self, context):
		_draw_bpm_ui(self.layout, context)



# ---------------------------------------------------------------------------
# UI Panel for the NLA Editor view
# ---------------------------------------------------------------------------

class NLA_PT_bpm_panel(bpy.types.Panel):
	bl_label = "BPM Overlay"
	bl_idname = "NLA_PT_bpm_panel"
	bl_space_type = "NLA_EDITOR"
	bl_region_type = "UI"
	bl_category = "Launch"
	bl_order = 21
	bl_options = {'DEFAULT_CLOSED'}
	category_preference = "overlays_category_nla"

	@classmethod
	def poll(cls, context):
		return context.area is not None and context.area.type == 'NLA_EDITOR'

	def draw_header(self, context):
		self.layout.prop(_overlay_scene(context).production_kit_settings, "bpm_show", text="")

	def draw(self, context):
		_draw_bpm_ui(self.layout, context)



# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

# Registered from the tab category set in the extension preferences
panels = [BPM_PT_panel, SEQUENCER_PT_bpm_panel, GRAPH_PT_bpm_panel, NLA_PT_bpm_panel]
_draw_handle = None
_draw_handle_sequencer = None
_draw_handle_graph = None
_draw_handle_nla = None


def register():
	utility_panel.register_panels(panels)

	global _draw_handle, _draw_handle_sequencer, _draw_handle_graph, _draw_handle_nla
	_draw_handle = bpy.types.SpaceDopeSheetEditor.draw_handler_add(
		draw_bpm_overlay, (), 'WINDOW', 'POST_PIXEL'
	)
	_draw_handle_sequencer = bpy.types.SpaceSequenceEditor.draw_handler_add(
		draw_bpm_overlay, (), 'WINDOW', 'POST_PIXEL'
	)
	_draw_handle_graph = bpy.types.SpaceGraphEditor.draw_handler_add(
		draw_bpm_overlay, (), 'WINDOW', 'POST_PIXEL'
	)
	_draw_handle_nla = bpy.types.SpaceNLA.draw_handler_add(
		draw_bpm_overlay, (), 'WINDOW', 'POST_PIXEL'
	)


def unregister():
	global _draw_handle, _draw_handle_sequencer, _draw_handle_graph, _draw_handle_nla
	if _draw_handle is not None:
		bpy.types.SpaceDopeSheetEditor.draw_handler_remove(_draw_handle, 'WINDOW')
		_draw_handle = None
	if _draw_handle_sequencer is not None:
		bpy.types.SpaceSequenceEditor.draw_handler_remove(_draw_handle_sequencer, 'WINDOW')
		_draw_handle_sequencer = None
	if _draw_handle_graph is not None:
		bpy.types.SpaceGraphEditor.draw_handler_remove(_draw_handle_graph, 'WINDOW')
		_draw_handle_graph = None
	if _draw_handle_nla is not None:
		bpy.types.SpaceNLA.draw_handler_remove(_draw_handle_nla, 'WINDOW')
		_draw_handle_nla = None

	utility_panel.unregister_panels(panels)


if __name__ == "__main__":
	try:
		unregister()
	except Exception:
		pass
	register()
