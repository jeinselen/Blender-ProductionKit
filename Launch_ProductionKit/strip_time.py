import bpy

from . import utility_panel


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
			('MANUAL', "Manual", "Enter a frame number"),
		],
		default='PLAYHEAD',
	)
	preserve_offsets: bpy.props.BoolProperty(
		name="Preserve Offsets",
		description="Move the selection together instead of aligning every selected strip to the target",
		default=False,
	)
	frame: bpy.props.IntProperty(
		name="Frame",
		description="Frame for the selected strip edge or selection edge",
		default=1,
	)

	def _status_text(self):
		edge_name = "Start" if self.edge == 'START' else "End"
		group_name = "Group " if self.preserve_offsets else ""
		value = self._frame_input or "…"
		return f"Set {group_name}{edge_name} Frame: {value}  |  Enter: Confirm, Backspace: Edit, Esc: Cancel"

	def _set_status_text(self, context, text=None):
		area = getattr(context, "area", None)
		if area is not None:
			area.header_text_set(text)
		workspace = getattr(context, "workspace", None)
		if workspace is not None:
			workspace.status_text_set(text)

	@classmethod
	def poll(cls, context):
		return context.area is not None and context.area.type == 'SEQUENCE_EDITOR' and bool(_selected_strips(context))

	def _target_frame(self, scene):
		if self.target == 'RANGE_START':
			return scene.frame_start
		if self.target == 'RANGE_END':
			return scene.frame_end
		if self.target == 'MANUAL':
			return self.frame
		return scene.frame_current

	def invoke(self, context, event):
		if self.target == 'MANUAL':
			self._frame_input = ""
			self._set_status_text(context, self._status_text())
			context.window_manager.modal_handler_add(self)
			return {'RUNNING_MODAL'}
		return self.execute(context)

	def modal(self, context, event):
		if event.type in {'ESC', 'RIGHTMOUSE'}:
			self._set_status_text(context)
			return {'CANCELLED'}

		if event.type in {'RET', 'NUMPAD_ENTER', 'SPACE'} and event.value == 'PRESS':
			if self._frame_input not in {"", "-"}:
				self.frame = int(self._frame_input)
				self._set_status_text(context)
				return self.execute(context)
			return {'RUNNING_MODAL'}

		if event.type == 'BACK_SPACE' and event.value == 'PRESS':
			self._frame_input = self._frame_input[:-1]
		elif event.value == 'PRESS':
			character = event.ascii
			if not character and event.type.startswith('NUMPAD_'):
				character = event.type.removeprefix('NUMPAD_')
			if character.isdigit():
				self._frame_input += character
			elif (character == '-' or event.type in {'MINUS', 'NUMPAD_MINUS'}) and not self._frame_input:
				self._frame_input = "-"

		self._set_status_text(context, self._status_text())
		return {'RUNNING_MODAL'}

	def execute(self, context):
		strips = [strip for strip in _selected_strips(context) if not getattr(strip, "lock", False)]
		if not strips:
			self.report({'WARNING'}, "Select at least one unlocked strip")
			return {'CANCELLED'}

		scene = _sequencer_scene(context)
		target = self._target_frame(scene)
		get_edge = (lambda strip: strip.frame_final_start) if self.edge == 'START' else (lambda strip: strip.frame_final_end)

		if self.preserve_offsets:
			anchor = min(get_edge(strip) for strip in strips) if self.edge == 'START' else max(get_edge(strip) for strip in strips)
			deltas = ((strip, target - anchor) for strip in strips)
		else:
			deltas = ((strip, target - get_edge(strip)) for strip in strips)

		for strip, delta in deltas:
			strip.frame_start += delta

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

		box = layout.box()
		box.label(text="Playhead")
		row = box.row(align=True)
		_snap_button(row, "Start  [", 'START', 'PLAYHEAD')
		_snap_button(row, "End  ]", 'END', 'PLAYHEAD')
		row = box.row(align=True)
		_snap_button(row, "Keep Offsets  ⇧[", 'START', 'PLAYHEAD', True)
		_snap_button(row, "Keep Offsets  ⇧]", 'END', 'PLAYHEAD', True)

		box = layout.box()
		box.label(text="Timeline Range")
		grid = box.grid_flow(columns=2, even_columns=True, even_rows=True, align=True)
		_snap_button(grid, "Start → Range Start", 'START', 'RANGE_START')
		_snap_button(grid, "Start → Range End", 'START', 'RANGE_END')
		_snap_button(grid, "End → Range Start", 'END', 'RANGE_START')
		_snap_button(grid, "End → Range End", 'END', 'RANGE_END')

		box = layout.box()
		box.label(text="Frame Number")
		grid = box.grid_flow(columns=2, even_columns=True, even_rows=True, align=True)
		_snap_button(grid, "Start…  \\", 'START', 'MANUAL')
		_snap_button(grid, "End…", 'END', 'MANUAL')
		_snap_button(grid, "Group Start…  ⇧\\ (|)", 'START', 'MANUAL', True)
		_snap_button(grid, "Group End…", 'END', 'MANUAL', True)


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
		_add_keymap_item(keymap, 'BACK_SLASH', 'START', target='MANUAL')
		_add_keymap_item(keymap, 'BACK_SLASH', 'START', target='MANUAL', preserve_offsets=True, shift=True)


def unregister():
	for keymap, keymap_item in keymaps:
		keymap.keymap_items.remove(keymap_item)
	keymaps.clear()

	utility_panel.unregister_panels(panels)
	for cls in reversed(classes):
		bpy.utils.unregister_class(cls)
