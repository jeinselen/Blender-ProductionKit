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
