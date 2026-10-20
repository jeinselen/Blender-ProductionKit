import math
import bpy

from . import utility_panel

# Global Settings
WIDTHS = (140.0, 200.0, 320.0)
GRID_SIZE = 20.0

# Internal Functions
def _selected_nodes(context):
	"""Return selected nodes from the node tree shown in this editor."""
	space = context.space_data
	if context.area.type != 'NODE_EDITOR' or space.type != 'NODE_EDITOR':
		return ()
	edit_tree = space.edit_tree
	if edit_tree is None:
		return ()
	return tuple(node for node in edit_tree.nodes if node.select)

def _active_node(context):
	"""Return the active node from the node tree shown in this editor."""
	space = context.space_data
	if context.area.type != 'NODE_EDITOR' or space.type != 'NODE_EDITOR':
		return None
	edit_tree = space.edit_tree
	if edit_tree is None:
		return None
	return edit_tree.nodes.active

def _round_to_grid(value):
	return math.floor((value / GRID_SIZE) + 0.5) * GRID_SIZE



# External Functions
class PRODUCTIONKIT_OT_set_node_width(bpy.types.Operator):
	"""Set widths for selected nodes in the visible node tree"""
	bl_idname = "production_kit.set_node_width"
	bl_label = "Set Node Width"
	bl_options = {'REGISTER', 'UNDO'}
	
	width: bpy.props.FloatProperty(options={'HIDDEN'})
	adaptive: bpy.props.BoolProperty(options={'HIDDEN'}, default=False)
	
	@classmethod
	def poll(cls, context):
		return bool(_selected_nodes(context))
	
	def execute(self, context):
		for node in _selected_nodes(context):
			node.width = min(WIDTHS, key=lambda width: abs(width - node.width)) if self.adaptive else self.width
		return {'FINISHED'}

class PRODUCTIONKIT_OT_align_node_location(bpy.types.Operator):
	"""Align selected nodes to a rounded location in the visible node tree"""
	bl_idname = "production_kit.align_node_location"
	bl_label = "Align Node Location"
	bl_options = {'REGISTER', 'UNDO'}
	
	direction: bpy.props.EnumProperty(
		items=(
			('LEFT', 'Left', 'Align to the leftmost X location'),
			('UP', 'Top', 'Align to the topmost Y location'),
			('RIGHT', 'Right', 'Align to the rightmost X location'),
			('DOWN', 'Bottom', 'Align to the bottommost Y location'),
			),
		options={'HIDDEN'},
		)
	
	@classmethod
	def poll(cls, context):
		return bool(_selected_nodes(context))
	
	def execute(self, context):
		nodes = _selected_nodes(context)
		if self.direction == 'LEFT':
			target = _round_to_grid(min(node.location.x for node in nodes))
			for node in nodes:
				node.location.x = target
		elif self.direction == 'RIGHT':
			target = _round_to_grid(max(node.location.x for node in nodes))
			for node in nodes:
				node.location.x = target
		elif self.direction == 'DOWN':
			target = _round_to_grid(min(node.location.y for node in nodes))
			for node in nodes:
				node.location.y = target
		else:
			target = _round_to_grid(max(node.location.y for node in nodes))
			for node in nodes:
				node.location.y = target
		return {'FINISHED'}

class PRODUCTIONKIT_OT_set_node_location_origin(bpy.types.Operator):
	"""Move selected nodes in the visible node tree to the origin"""
	bl_idname = "production_kit.set_node_location_origin"
	bl_label = "Set Node Location to Origin"
	bl_options = {'REGISTER', 'UNDO'}
	
	@classmethod
	def poll(cls, context):
		return bool(_selected_nodes(context))
	
	def execute(self, context):
		for node in _selected_nodes(context):
			node.location = (0.0, 0.0)
		return {'FINISHED'}

class PRODUCTIONKIT_MT_node_layout(bpy.types.Menu):
	bl_idname = "PRODUCTIONKIT_MT_node_layout"
	bl_label = "Layout"
	
	def draw(self, context):
		layout = self.layout
		operator = layout.operator(PRODUCTIONKIT_OT_set_node_width.bl_idname, text="Set Width to Nearest Preset")
		operator.adaptive = True
		layout.separator()
		for width in WIDTHS:
			operator = layout.operator(PRODUCTIONKIT_OT_set_node_width.bl_idname, text=f"Set Width to {int(width)}")
			operator.width = width
		layout.separator()
		for direction, label in (('LEFT', 'Align Left'), ('UP', 'Align Top'), ('RIGHT', 'Align Right'), ('DOWN', 'Align Bottom')):
			operator = layout.operator(PRODUCTIONKIT_OT_align_node_location.bl_idname, text=label)
			operator.direction = direction
		layout.separator()
		layout.operator(PRODUCTIONKIT_OT_set_node_location_origin.bl_idname, text="Set Location to Origin")

def draw_node_menu(self, context):
	self.layout.menu(PRODUCTIONKIT_MT_node_layout.bl_idname)


class PRODUCTIONKIT_PT_node_layout(bpy.types.Panel):
	"""Display and edit the active node's layout values"""
	bl_idname = "PRODUCTIONKIT_PT_node_layout"
	bl_label = "Node Layout"
	bl_space_type = 'NODE_EDITOR'
	bl_region_type = 'UI'
	bl_category = "Node"
	bl_options = {'DEFAULT_CLOSED'}
	category_preference = "node_layout_category"
	
	@classmethod
	def poll(cls, context):
		return _active_node(context) is not None
	
	def draw(self, context):
		node = _active_node(context)
		layout = self.layout
#		layout.use_property_decorate = False
#		layout.use_property_split = False
		
		anchor = layout.split(factor=0.2)
		label = anchor.column()
		label.label(text="Position")
		label.label(text="Width")
		label.label(text="Align")
		items = anchor.column()
		
		row = items.row(align=True)
		row.prop(node, "location", index=0, text="")
		row.prop(node, "location", index=1, text="")
		row.prop(node, "width", text="")
		
		row = items.row(align=True)
		operator = row.operator(PRODUCTIONKIT_OT_set_node_width.bl_idname, text="Nearest")
		operator.adaptive = True
		for width in WIDTHS:
			operator = row.operator(PRODUCTIONKIT_OT_set_node_width.bl_idname, text=str(int(width)))
			operator.width = width
			
		row = items.row(align=True)
		for direction, text in (('LEFT', '←'), ('UP', '↑'), ('RIGHT', '→'), ('DOWN', '↓')):
			operator = row.operator(PRODUCTIONKIT_OT_align_node_location.bl_idname, text=text)
			operator.direction = direction
		row.operator(PRODUCTIONKIT_OT_set_node_location_origin.bl_idname, text="0")
		
		



# Registration
classes = (
	PRODUCTIONKIT_OT_set_node_width,
	PRODUCTIONKIT_OT_align_node_location,
	PRODUCTIONKIT_OT_set_node_location_origin,
	PRODUCTIONKIT_MT_node_layout,
	)

panels = [
	PRODUCTIONKIT_PT_node_layout,
	]

keymaps = []

def _add_keymap_item(keymap, operator, key, **properties):
	keymap_item = keymap.keymap_items.new(operator, key, 'PRESS', oskey=True, alt=True)
	for name, value in properties.items():
		setattr(keymap_item.properties, name, value)
	keymaps.append((keymap, keymap_item))

def register():
	for cls in classes:
		bpy.utils.register_class(cls)
	bpy.types.NODE_MT_node.append(draw_node_menu)
	utility_panel.register_panels(panels)
	
	keymap = bpy.context.window_manager.keyconfigs.addon.keymaps.new(name='Node Editor', space_type='NODE_EDITOR')
	_add_keymap_item(keymap, PRODUCTIONKIT_OT_set_node_width.bl_idname, 'ACCENT_GRAVE', adaptive=True)
	_add_keymap_item(keymap, PRODUCTIONKIT_OT_set_node_width.bl_idname, 'ONE', width=140.0)
	_add_keymap_item(keymap, PRODUCTIONKIT_OT_set_node_width.bl_idname, 'TWO', width=200.0)
	_add_keymap_item(keymap, PRODUCTIONKIT_OT_set_node_width.bl_idname, 'THREE', width=320.0)
	_add_keymap_item(keymap, PRODUCTIONKIT_OT_align_node_location.bl_idname, 'LEFT_ARROW', direction='LEFT')
	_add_keymap_item(keymap, PRODUCTIONKIT_OT_align_node_location.bl_idname, 'UP_ARROW', direction='UP')
	_add_keymap_item(keymap, PRODUCTIONKIT_OT_align_node_location.bl_idname, 'RIGHT_ARROW', direction='RIGHT')
	_add_keymap_item(keymap, PRODUCTIONKIT_OT_align_node_location.bl_idname, 'DOWN_ARROW', direction='DOWN')
	_add_keymap_item(keymap, PRODUCTIONKIT_OT_set_node_location_origin.bl_idname, 'ZERO')

def unregister():
	for keymap, keymap_item in keymaps:
		keymap.keymap_items.remove(keymap_item)
	keymaps.clear()
	
	utility_panel.unregister_panels(panels)
	bpy.types.NODE_MT_node.remove(draw_node_menu)
	for cls in reversed(classes):
		bpy.utils.unregister_class(cls)
		