import bpy

###########################################################################
# Main class

class PRODUCTIONKIT_OT_set_viewport_shading(bpy.types.Operator):
	bl_idname = "view3d.vfviewportshading"
	bl_label = "Set Viewport Shading"
	bl_description = "Sets viewport shading mode"
	bl_space_type = "VIEW_3D"
	bl_region_type = 'UI'
	
	rendertype: bpy.props.StringProperty()
	
	def invoke(self, context, event):
		context.area.spaces[0].shading.type = self.rendertype
#		context.space_data.shading.type = self.rendertype
		return {'FINISHED'}

###########################################################################
# Menu UI

def production_kit_viewport_shading_menu_items(self, context):
	self.layout.separator()
	op0 = self.layout.operator(PRODUCTIONKIT_OT_set_viewport_shading.bl_idname, text = "Wireframe", icon = "SHADING_WIRE")
	op0.rendertype = "WIREFRAME"
	op1 = self.layout.operator(PRODUCTIONKIT_OT_set_viewport_shading.bl_idname, text = "Solid", icon = "SHADING_SOLID")
	op1.rendertype = "SOLID"
	op2 = self.layout.operator(PRODUCTIONKIT_OT_set_viewport_shading.bl_idname, text = "Preview", icon = "SHADING_TEXTURE")
	op2.rendertype = "MATERIAL"
	op3 = self.layout.operator(PRODUCTIONKIT_OT_set_viewport_shading.bl_idname, text = "Rendered", icon = "SHADING_RENDERED")
	op3.rendertype = "RENDERED"



# ---------------------------------------------------------------------------
# Register classes
# ---------------------------------------------------------------------------

classes = [
	PRODUCTIONKIT_OT_set_viewport_shading,
]

keymaps = []


def register():
	for cls in classes:
		bpy.utils.register_class(cls)
	bpy.types.VIEW3D_MT_view.append(production_kit_viewport_shading_menu_items)

	wm = bpy.context.window_manager
	kc = wm.keyconfigs.addon
	if kc:
		km = wm.keyconfigs.addon.keymaps.new(name='3D View', space_type='VIEW_3D')
		kmi = km.keymap_items.new(PRODUCTIONKIT_OT_set_viewport_shading.bl_idname, 'NUMPAD_1', 'PRESS')
#		kmi = km.keymap_items.new(PRODUCTIONKIT_OT_set_viewport_shading.bl_idname, 'F1', 'PRESS', alt=True)
		kmi.properties.rendertype = 'WIREFRAME'
		keymaps.append((km, kmi))

		km = wm.keyconfigs.addon.keymaps.new(name='3D View', space_type='VIEW_3D')
		kmi = km.keymap_items.new(PRODUCTIONKIT_OT_set_viewport_shading.bl_idname, 'NUMPAD_2', 'PRESS')
#		kmi = km.keymap_items.new(PRODUCTIONKIT_OT_set_viewport_shading.bl_idname, 'F2', 'PRESS', alt=True)
		kmi.properties.rendertype = 'SOLID'
		keymaps.append((km, kmi))

		km = wm.keyconfigs.addon.keymaps.new(name='3D View', space_type='VIEW_3D')
		kmi = km.keymap_items.new(PRODUCTIONKIT_OT_set_viewport_shading.bl_idname, 'NUMPAD_3', 'PRESS')
#		kmi = km.keymap_items.new(PRODUCTIONKIT_OT_set_viewport_shading.bl_idname, 'F3', 'PRESS', alt=True)
		kmi.properties.rendertype = 'MATERIAL'
		keymaps.append((km, kmi))

		km = wm.keyconfigs.addon.keymaps.new(name='3D View', space_type='VIEW_3D')
		kmi = km.keymap_items.new(PRODUCTIONKIT_OT_set_viewport_shading.bl_idname, 'NUMPAD_0', 'PRESS')
#		kmi = km.keymap_items.new(PRODUCTIONKIT_OT_set_viewport_shading.bl_idname, 'F4', 'PRESS', alt=True)
		kmi.properties.rendertype = 'RENDERED'
		keymaps.append((km, kmi))


def unregister():
	for km, kmi in keymaps:
		km.keymap_items.remove(kmi)
	keymaps.clear()
	bpy.types.VIEW3D_MT_view.remove(production_kit_viewport_shading_menu_items)
	for cls in reversed(classes):
		bpy.utils.unregister_class(cls)


if __name__ == "__main__":
	register()
