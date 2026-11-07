import bpy
from . import utility_panel



# Functions

def _sequencer_scene(context):
	"""Return the scene displayed by the Sequencer when available."""
	return getattr(context, "sequencer_scene", None) or context.scene

def _selected_strips(context):
	"""Return the selected strips from a Sequencer context."""
	selected = getattr(context, "selected_strips", None)
	if selected is not None:
		return list(selected)

	scene = _sequencer_scene(context)
	editor = getattr(scene, "sequence_editor", None)
	if editor is None:
		return []
	return [strip for strip in editor.strips_all if strip.select]

def _unlocked_selected_strips(context):
	return [strip for strip in _selected_strips(context) if not getattr(strip, "lock", False)]

def _move_strips_to_frame(context, edge, target_frame, preserve_offsets):
	"""Move each unlocked selected strip so its given edge lands on target_frame.
	With preserve_offsets, the whole selection is shifted together instead, using
	the earliest start (or latest end) among the selection as the moving edge.
	Returns False when there was nothing selected to move."""
	strips = _unlocked_selected_strips(context)
	if not strips:
		return False

	get_edge = (lambda strip: strip.frame_final_start) if edge == 'START' else (lambda strip: strip.frame_final_end)

	if preserve_offsets:
		anchor = min(get_edge(strip) for strip in strips) if edge == 'START' else max(get_edge(strip) for strip in strips)
		deltas = ((strip, target_frame - anchor) for strip in strips)
	else:
		deltas = ((strip, target_frame - get_edge(strip)) for strip in strips)

	for strip, delta in deltas:
		strip.frame_start += delta
	return True

def _edge_frame(context, edge):
	"""Current position of the given edge across the selection: the earliest start,
	or the latest end, among selected unlocked strips. Falls back to the current
	frame when nothing is selected, so the field has a sane value to display."""
	strips = _unlocked_selected_strips(context)
	if not strips:
		return _sequencer_scene(context).frame_current
	get_edge = (lambda strip: strip.frame_final_start) if edge == 'START' else (lambda strip: strip.frame_final_end)
	values = [get_edge(strip) for strip in strips]
	return min(values) if edge == 'START' else max(values)

def get_start_frame(self):
	return _edge_frame(bpy.context, 'START')

def set_start_frame(self, value):
	_move_strips_to_frame(bpy.context, 'START', value, self.strip_time_group)

def get_end_frame(self):
	return _edge_frame(bpy.context, 'END')

def set_end_frame(self, value):
	_move_strips_to_frame(bpy.context, 'END', value, self.strip_time_group)

def _apply_numeric_value(context, get_value, set_value, target_value, group, use_max_anchor):
	"""Apply a user-entered value to every unlocked selected strip via get_value/set_value
	accessors. With group, the whole selection is shifted together by the same delta,
	anchored on the earliest (or latest, with use_max_anchor) existing value; otherwise
	every strip is set to target_value directly. Returns False when nothing is selected."""
	strips = _unlocked_selected_strips(context)
	if not strips:
		return False
	if group:
		anchor = (max if use_max_anchor else min)(get_value(strip) for strip in strips)
		delta = target_value - anchor
		for strip in strips:
			set_value(strip, get_value(strip) + delta)
	else:
		for strip in strips:
			set_value(strip, target_value)
	return True

def _media_in_frame(strip):
	"""Source media frame shown at the strip's trimmed start (0-based, before any trim this is 0)."""
	return int(strip.left_handle_offset)

def _set_media_in_frame(strip, value):
	strip.left_handle_offset = value

def _media_out_frame(strip):
	"""Source media frame shown at the strip's trimmed end (0-based, inclusive)."""
	return int(strip.content_duration) - 1 - int(strip.right_handle_offset)

def _set_media_out_frame(strip, value):
	strip.right_handle_offset = strip.content_duration - 1 - value

def _media_edge_value(context, get_value, use_max_anchor):
	strips = _unlocked_selected_strips(context)
	if not strips:
		return 0
	values = [get_value(strip) for strip in strips]
	return max(values) if use_max_anchor else min(values)

def get_in_frame(self):
	return _media_edge_value(bpy.context, _media_in_frame, use_max_anchor=False)

def set_in_frame(self, value):
	_apply_numeric_value(bpy.context, _media_in_frame, _set_media_in_frame, value, self.strip_time_group, use_max_anchor=False)

def get_out_frame(self):
	return _media_edge_value(bpy.context, _media_out_frame, use_max_anchor=True)

def set_out_frame(self, value):
	_apply_numeric_value(bpy.context, _media_out_frame, _set_media_out_frame, value, self.strip_time_group, use_max_anchor=True)



# Classes

class PRODUCTIONKIT_OT_snap_strip_time(bpy.types.Operator):
	"""Snap selected strip edges to a known timeline frame"""
	bl_idname = "sequencer.productionkit_snap_strip_time"
	bl_label = "Snap Strip Time"
	bl_options = {'REGISTER', 'UNDO'}
	
	edge: bpy.props.EnumProperty(
		name="Strip Edge",
		description="Strip edge to snap",
		items=[
			('START', "Start", "Snap the visible start of each strip"),
			('END', "End", "Snap the visible end of each strip"),
		],
		default='START',
	)
	target: bpy.props.EnumProperty(
		name="Target",
		description="Timeline position used as the snap target",
		items=[
			('PLAYHEAD', "Playhead", "Use the current frame"),
			('RANGE_START', "Range Start", "Use the timeline start frame"),
			('RANGE_END', "Range End", "Use the timeline end frame"),
		],
		default='PLAYHEAD',
	)
	preserve_offsets: bpy.props.BoolProperty(
		name="Preserve Offsets",
		description="Move the selection together instead of aligning every selected strip to the target",
		default=False,
	)
	
	@classmethod
	def poll(cls, context):
		return context.area is not None and context.area.type == 'SEQUENCE_EDITOR' and bool(_selected_strips(context))
	
	def _target_frame(self, scene):
		if self.target == 'RANGE_START':
			return scene.frame_start
		if self.target == 'RANGE_END':
			return scene.frame_end
		return scene.frame_current
	
	def execute(self, context):
		scene = _sequencer_scene(context)
		target = self._target_frame(scene)
		if not _move_strips_to_frame(context, self.edge, target, self.preserve_offsets):
			self.report({'WARNING'}, "Select at least one unlocked strip")
			return {'CANCELLED'}
		return {'FINISHED'}


def _snap_button(layout, text, edge, target, preserve_offsets=False):
	operator = layout.operator(PRODUCTIONKIT_OT_snap_strip_time.bl_idname, text=text)
	operator.edge = edge
	operator.target = target
	operator.preserve_offsets = preserve_offsets


class PRODUCTIONKIT_PT_strip_time(bpy.types.Panel):
	"""Strip timing controls for the Video Sequencer"""
	bl_idname = "PRODUCTIONKIT_PT_strip_time"
	bl_label = "Strip Time"
	bl_space_type = 'SEQUENCE_EDITOR'
	bl_region_type = 'UI'
	bl_category = "Tool"
	bl_options = {'DEFAULT_CLOSED'}
	category_preference = "strip_time_category"
	
	@classmethod
	def poll(cls, context):
		return context.area is not None and context.area.type == 'SEQUENCE_EDITOR'
	
	def draw(self, context):
		layout = self.layout
		
		layout.label(text="Playhead")
		grid = layout.grid_flow(row_major=True, columns=2, even_columns=True, even_rows=True, align=True)
		_snap_button(grid, "Start  [", 'START', 'PLAYHEAD')
		_snap_button(grid, "End  ]", 'END', 'PLAYHEAD')
		_snap_button(grid, "Keep Offsets  ⇧[", 'START', 'PLAYHEAD', True)
		_snap_button(grid, "Keep Offsets  ⇧]", 'END', 'PLAYHEAD', True)
		
		layout.label(text="Timeline Start")
		grid = layout.grid_flow(row_major=True, columns=2, even_columns=True, even_rows=True, align=True)
		_snap_button(grid, "Start → Range Start", 'START', 'RANGE_START')
		_snap_button(grid, "End → Range Start", 'END', 'RANGE_START')
		_snap_button(grid, "Keep Offsets", 'START', 'RANGE_START', True)
		_snap_button(grid, "Keep Offsets", 'END', 'RANGE_START', True)
		
		layout.label(text="Timeline End")
		grid = layout.grid_flow(row_major=True, columns=2, even_columns=True, even_rows=True, align=True)
		_snap_button(grid, "Start → Range End", 'START', 'RANGE_END')
		_snap_button(grid, "End → Range End", 'END', 'RANGE_END')
		_snap_button(grid, "Keep Offsets", 'START', 'RANGE_END', True)
		_snap_button(grid, "Keep Offsets", 'END', 'RANGE_END', True)
		
		settings = context.scene.production_kit_settings
		has_selection = bool(_selected_strips(context))
		
		layout.label(text="Clip Details")
		grid = layout.grid_flow(row_major=True, columns=2, even_columns=True, even_rows=True, align=True)
		grid.enabled = has_selection
		grid.prop(settings, "strip_time_start", text="Start")
		grid.prop(settings, "strip_time_end", text="End")
		grid.prop(settings, "strip_time_in", text="Trim In")
		grid.prop(settings, "strip_time_out", text="Trim Out")
		grid.separator()
		grid.prop(settings, "strip_time_group")



# Registration

classes = (
	PRODUCTIONKIT_OT_snap_strip_time,
)

panels = [
	PRODUCTIONKIT_PT_strip_time,
]

keymaps = []


def _add_keymap_item(keymap, key, edge, target='PLAYHEAD', preserve_offsets=False, shift=False):
	keymap_item = keymap.keymap_items.new(
		PRODUCTIONKIT_OT_snap_strip_time.bl_idname,
		key,
		'PRESS',
		shift=shift,
	)
	keymap_item.properties.edge = edge
	keymap_item.properties.target = target
	keymap_item.properties.preserve_offsets = preserve_offsets
	keymaps.append((keymap, keymap_item))


def register():
	for cls in classes:
		bpy.utils.register_class(cls)
	utility_panel.register_panels(panels)

	keyconfig = bpy.context.window_manager.keyconfigs.addon
	if keyconfig:
		keymap = keyconfig.keymaps.new(name='Sequencer', space_type='SEQUENCE_EDITOR')
		_add_keymap_item(keymap, 'LEFT_BRACKET', 'START')
		_add_keymap_item(keymap, 'RIGHT_BRACKET', 'END')
		_add_keymap_item(keymap, 'LEFT_BRACKET', 'START', preserve_offsets=True, shift=True)
		_add_keymap_item(keymap, 'RIGHT_BRACKET', 'END', preserve_offsets=True, shift=True)


def unregister():
	for keymap, keymap_item in keymaps:
		keymap.keymap_items.remove(keymap_item)
	keymaps.clear()

	utility_panel.unregister_panels(panels)
	for cls in reversed(classes):
		bpy.utils.unregister_class(cls)
