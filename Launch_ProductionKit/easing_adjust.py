import bpy

from . import utility_panel

# Handle types whose position isn't independently free: AUTO/AUTO_CLAMPED/VECTOR are
# recalculated from neighbouring keyframes, and ALIGNED is kept collinear with its
# opposite handle — all three would silently discard or distort a manual override
NON_FREE_HANDLE_TYPES = {'AUTO', 'AUTO_CLAMPED', 'VECTOR', 'ALIGNED'}



# Internal Functions
def _iter_selected_keyframes(context):
	"""Yield (fcurve, points, index, keyframe) for each selected keyframe in the editor's visible, editable F-curves"""
	fcurves = getattr(context, "selected_editable_fcurves", None)
	if not fcurves:
		return
	for fcurve in fcurves:
		points = fcurve.keyframe_points
		for index, keyframe in enumerate(points):
			if keyframe.select_control_point:
				yield fcurve, points, index, keyframe

def _incoming_delta(points, index, axis):
	"""Distance from the previous keyframe to the current one, on the given axis (0=time, 1=value).
	When there's no previous keyframe, mirror the following keyframe's distance instead.
	Returns None if neither neighbour exists (a single isolated keyframe)."""
	keyframe = points[index]
	if index > 0:
		return keyframe.co[axis] - points[index - 1].co[axis]
	elif index < len(points) - 1:
		return points[index + 1].co[axis] - keyframe.co[axis]
	return None

def _outgoing_delta(points, index, axis):
	"""Distance from the current keyframe to the following one, on the given axis (0=time, 1=value).
	When there's no following keyframe, mirror the previous keyframe's distance instead.
	Returns None if neither neighbour exists (a single isolated keyframe)."""
	keyframe = points[index]
	if index < len(points) - 1:
		return points[index + 1].co[axis] - keyframe.co[axis]
	elif index > 0:
		return keyframe.co[axis] - points[index - 1].co[axis]
	return None

def _any_selected_keyframe(context):
	return any(True for _ in _iter_selected_keyframes(context))

def _apply(context, overrides):
	"""Apply one or more (incoming, axis, value) handle overrides — axis 0=time, 1=value —
	to all eligible selected keyframes, in a single pass. Returns the number of overrides
	actually applied (0 if every eligible keyframe/override combination was skipped).
	
	Note: fcurve.update() is deliberately never called here — it recalculates handle
	positions for AUTO/AUTO_CLAMPED/VECTOR/ALIGNED keyframes, including the untouched
	opposite handle of the one just edited, which would overwrite this override with
	a value derived from it instead of the one we just set"""
	applied = 0
	for fcurve, points, index, keyframe in _iter_selected_keyframes(context):
		for incoming, axis, value in overrides:
			if incoming:
				delta = _incoming_delta(points, index, axis)
				if delta is None:
					continue
				if keyframe.handle_left_type in NON_FREE_HANDLE_TYPES:
					keyframe.handle_left_type = 'FREE'
				keyframe.handle_left[axis] = keyframe.co[axis] + value * delta
			else:
				delta = _outgoing_delta(points, index, axis)
				if delta is None:
					continue
				if keyframe.handle_right_type in NON_FREE_HANDLE_TYPES:
					keyframe.handle_right_type = 'FREE'
				keyframe.handle_right[axis] = keyframe.co[axis] + value * delta
			applied += 1
	return applied

# Blender's own built-in handle types, in the same order and with the same icons as the
# Graph Editor / Dope Sheet "Handle Type" context menu (Key menu, or press V)
HANDLE_TYPES = (
	('FREE', 'HANDLE_FREE'),
	('ALIGNED', 'HANDLE_ALIGNED'),
	('VECTOR', 'HANDLE_VECTOR'),
	('AUTO', 'HANDLE_AUTO'),
	('AUTO_CLAMPED', 'HANDLE_AUTOCLAMPED'),
	)

def _draw_handle_type_row(layout, context):
	"""Row of Blender's own built-in handle type operators, resetting selected keyframes to a standard type"""
	idname = "graph.handle_type" if context.area.type == 'GRAPH_EDITOR' else "action.handle_type"
	row = layout.grid_flow(row_major=True, columns=5, even_columns=True, align=True)
	for handle_type, icon in HANDLE_TYPES:
		row.operator(idname, text="", icon=icon).type = handle_type

PRESET_FACTORS = (0.1, 0.25, 0.333333, 0.5, 0.666666, 0.75, 0.9)

def _format_factor(factor):
	return f"{factor:.2f}".rstrip('0').rstrip('.')

def _draw_preset_row(layout, enabled, value):
	"""Row of time-factor preset buttons, all using the given flat/full value factor (0 or 1)"""
	row = layout.grid_flow(row_major=True, columns=7, even_columns=True, align=True)
	row.enabled = enabled
	for factor in PRESET_FACTORS:
		op = row.operator(PRODUCTIONKIT_OT_easing_adjust.bl_idname, text=_format_factor(factor))
		op.target = 'ALL'
		op.use_preset = True
		op.factor = factor
		op.value = value

def _mirror_axis(settings, axis):
	"""Mirror the outgoing slider onto incoming for one axis (0=time, 1=value), writing the
	result back to the stored incoming setting. Returns the two overrides (outgoing, incoming)"""
	outgoing_value = settings.easing_outgoing_x if axis == 0 else settings.easing_outgoing_y
	if axis == 0:
		settings.easing_incoming_x = -outgoing_value
	else:
		settings.easing_incoming_y = -outgoing_value
	return [(False, axis, outgoing_value), (True, axis, -outgoing_value)]

def _draw_adjust_button(layout, enabled, icon, target, text=""):
	"""A single Adjust Easing button, as its own enabled/disabled sub-row"""
	sub = layout.row(align=True)
	sub.enabled = enabled
	sub.operator(PRODUCTIONKIT_OT_easing_adjust.bl_idname, text=text, icon=icon).target = target

def _handle_status(context):
	"""Return (any_possible, any_skipped) for selected keyframes with/without any usable
	neighbour. Identical for incoming and outgoing — both fail only on a single isolated
	keyframe — so one pass covers both"""
	possible = False
	skipped = False
	for fcurve, points, index, keyframe in _iter_selected_keyframes(context):
		if len(points) > 1:
			possible = True
		else:
			skipped = True
	return possible, skipped



# External Functions
class PRODUCTIONKIT_OT_easing_adjust(bpy.types.Operator):
	"""Override the handle position of selected keyframes, relative to the neighbouring keyframe"""
	bl_idname = "production_kit.easing_adjust"
	bl_label = "Adjust Easing Handle"
	bl_options = {'REGISTER', 'UNDO'}
	
	target: bpy.props.EnumProperty(
		items=(
			('INCOMING_X', 'Incoming X', ''),
			('INCOMING_Y', 'Incoming Y', ''),
			('OUTGOING_X', 'Outgoing X', ''),
			('OUTGOING_Y', 'Outgoing Y', ''),
			('SYMMETRIC_X', 'Symmetric X', ''),
			('SYMMETRIC_Y', 'Symmetric Y', ''),
			('ALL', 'All', ''),
			),
		options={'HIDDEN', 'SKIP_SAVE'},
		default='ALL',
		)
	# Preset mode: write factor/value into the sliders (as -factor/factor and -value/value)
	# before reading them, instead of applying the sliders' current values as-is.
	# SKIP_SAVE is required on all four properties here: without it, Blender remembers
	# the last value used for each property across separate button presses (they all
	# share one operator), so a preset click would leave use_preset/factor/value stuck
	# and silently re-triggered by the next unrelated button (e.g. an individual axis
	# apply), overwriting manually-adjusted sliders with the old preset's values
	use_preset: bpy.props.BoolProperty(options={'HIDDEN', 'SKIP_SAVE'}, default=False)
	factor: bpy.props.FloatProperty(options={'HIDDEN', 'SKIP_SAVE'}, min=0.0, max=1.0)
	value: bpy.props.FloatProperty(options={'HIDDEN', 'SKIP_SAVE'}, min=0.0, max=1.0)
	
	@classmethod
	def poll(cls, context):
		return _any_selected_keyframe(context)
	
	def execute(self, context):
		settings = context.scene.production_kit_settings
		
		if self.use_preset:
			settings.easing_incoming_x = -self.factor
			settings.easing_incoming_y = -self.value
			settings.easing_outgoing_x = self.factor
			settings.easing_outgoing_y = self.value
		
		if self.target == 'ALL' and settings.easing_mode == 'SYMMETRIC':
			overrides = _mirror_axis(settings, 0) + _mirror_axis(settings, 1)
		elif self.target == 'ALL':
			overrides = [
				(True, 0, settings.easing_incoming_x),
				(True, 1, settings.easing_incoming_y),
				(False, 0, settings.easing_outgoing_x),
				(False, 1, settings.easing_outgoing_y),
				]
		elif self.target.startswith('SYMMETRIC'):
			overrides = _mirror_axis(settings, 0 if self.target.endswith('_X') else 1)
		else:
			incoming = self.target.startswith('INCOMING')
			axis = 0 if self.target.endswith('_X') else 1
			value = {
				'INCOMING_X': settings.easing_incoming_x,
				'INCOMING_Y': settings.easing_incoming_y,
				'OUTGOING_X': settings.easing_outgoing_x,
				'OUTGOING_Y': settings.easing_outgoing_y,
				}[self.target]
			overrides = [(incoming, axis, value)]
		
		if _apply(context, overrides) == 0:
			self.report({'WARNING'}, "No eligible keyframes")
			return {'CANCELLED'}
		
		return {'FINISHED'}



def _draw_easing_ui(layout, context):
	"""Shared UI drawing for the Easing Adjust panel — used in both the Graph Editor and Dope Sheet"""
	settings = context.scene.production_kit_settings
	
	# Logic
	handle_ok, handle_skip = _handle_status(context)
	
	# Primary layout
	col = layout.column(align=True)
	
	# Reset Easing
	col.label(text="Reset Handles")
	_draw_handle_type_row(col, context)
	
	# Adjust Easing
	col.separator()
	col.label(text="Adjust Easing")
	col.row(align=True).prop(settings, "easing_mode", expand=True)
	col.separator()
	
	if settings.easing_mode == 'SYMMETRIC':
		row = col.row(align=True)
		_draw_adjust_button(row, handle_ok, "ARROW_LEFTRIGHT", 'SYMMETRIC_X')
		row.prop(settings, "easing_outgoing_x", text="X")
		
		row = col.row(align=True)
		_draw_adjust_button(row, handle_ok, "ARROW_LEFTRIGHT", 'SYMMETRIC_Y')
		row.prop(settings, "easing_outgoing_y", text="Y")
	else:
		row = col.row(align=True)
		row.prop(settings, "easing_incoming_x", text="X")
		_draw_adjust_button(row, handle_ok, "PREV_KEYFRAME", 'INCOMING_X')
		_draw_adjust_button(row, handle_ok, "NEXT_KEYFRAME", 'OUTGOING_X')
		row.prop(settings, "easing_outgoing_x", text="X")
		
		row = col.row(align=True)
		row.prop(settings, "easing_incoming_y", text="Y")
		_draw_adjust_button(row, handle_ok, "PREV_KEYFRAME", 'INCOMING_Y')
		_draw_adjust_button(row, handle_ok, "NEXT_KEYFRAME", 'OUTGOING_Y')
		row.prop(settings, "easing_outgoing_y", text="Y")
	
	# Isolated Keyframe Alert
	if handle_ok and handle_skip:
		col.label(text="Single keyframes ignored", icon='INFO')
	
	# Apply All
	col.separator()
	_draw_adjust_button(col, handle_ok, "ARROW_LEFTRIGHT", 'ALL', text="Apply All")
	
	# Preset Easing
	col.separator()
	col.label(text="Ease Flat")
	_draw_preset_row(col, handle_ok, 0.0)
	col.label(text="Ease Angle")
	_draw_preset_row(col, handle_ok, 1.0)



class PRODUCTIONKIT_PT_easing_graph(bpy.types.Panel):
	"""Keyframe handle easing overrides for the Graph Editor"""
	bl_idname = "PRODUCTIONKIT_PT_easing_graph"
	bl_label = "Easing Adjust"
	bl_space_type = 'GRAPH_EDITOR'
	bl_region_type = 'UI'
	bl_category = "View"
	category_preference = "easing_category_graph"
	
	def draw(self, context):
		_draw_easing_ui(self.layout, context)



class PRODUCTIONKIT_PT_easing_dopesheet(bpy.types.Panel):
	"""Keyframe handle easing overrides for the Dope Sheet (all modes except Timeline, which has no sidebar)"""
	bl_idname = "PRODUCTIONKIT_PT_easing_dopesheet"
	bl_label = "Easing Adjust"
	bl_space_type = 'DOPESHEET_EDITOR'
	bl_region_type = 'UI'
	bl_category = "View"
	category_preference = "easing_category_dopesheet"
	
	@classmethod
	def poll(cls, context):
		return context.space_data.mode != 'TIMELINE'
	
	def draw(self, context):
		_draw_easing_ui(self.layout, context)



# Registration
classes = (
	PRODUCTIONKIT_OT_easing_adjust,
	)

panels = [
	PRODUCTIONKIT_PT_easing_graph,
	PRODUCTIONKIT_PT_easing_dopesheet,
	]

def register():
	for cls in classes:
		bpy.utils.register_class(cls)
	utility_panel.register_panels(panels)

def unregister():
	utility_panel.unregister_panels(panels)
	for cls in reversed(classes):
		bpy.utils.unregister_class(cls)
